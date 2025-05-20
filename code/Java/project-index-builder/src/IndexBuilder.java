import org.apache.lucene.analysis.Analyzer;
import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.document.Field;
import org.apache.lucene.document.SortedSetDocValuesField;
import org.apache.lucene.document.StoredField;
import org.apache.lucene.document.StringField;
import org.apache.lucene.index.IndexWriter;
import org.apache.lucene.index.IndexWriterConfig;
import org.apache.lucene.index.IndexWriterConfig.OpenMode;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.FSDirectory;
import org.apache.lucene.util.BytesRef;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.io.FileInputStream;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Map;

/**
 * Index Builder class - used to add documents and build Lucene index
 */
public class IndexBuilder {
    private final Path code_info_path;
    private final Path index_path;
    private Analyzer analyzer;
    private Directory directory;
    private IndexWriter index_writer;

    public static void main(String[] args) {
        int arg_len = args.length;
        if (arg_len < 3) {
            throw new IllegalArgumentException("Arguments for IndexBuilder:<mode> <project path> <index path>");
        }
        String mode = args[0];
        Path code_path = Paths.get(args[1]);
        Path index_path = Paths.get(args[2]);

        if (mode.equals("single")) {
            IndexBuilder builder = new IndexBuilder(code_path, index_path);
            builder.startSingle(code_path, index_path);
        } else if (mode.equals("group")) {
            if (!Files.isDirectory(code_path)){
                throw new IllegalArgumentException("project root should be a directory!");
            }
            IndexBuilder builder = new IndexBuilder(code_path, index_path);
            builder.startGroup();
        } else {
            throw new IllegalArgumentException("Usage for mode: single or group" + mode);
        }
    }

    /**
     * initializes the index builder
     * @param indexPath Path to store the index
     */
    public IndexBuilder(Path project_root, Path index_path) {
        this.index_path = index_path;
        this.code_info_path = project_root;
    }

    /**
     * Parse the source code info from json file
     */
    protected void ParseSourceCodeInfo(Path file_path){
        JsonObject code_info;
        try{
            code_info = loadJson(file_path).getAsJsonObject();
        } catch (Exception e) {
            System.out.println("Failed to load json file: " + code_info_path);
            System.out.println(e.getMessage());
            return;
        }
        JsonObject source_info = code_info.getAsJsonObject("source");
        for (Map.Entry<String, JsonElement> class_entry : source_info.entrySet()) {
            String class_fqn = class_entry.getKey();
            JsonObject class_info = class_entry.getValue().getAsJsonObject();
            String file = class_info.get("file").getAsString();
            JsonObject methods = class_info.get("methods").getAsJsonObject();
            // Traverse all method information and get method details
            methods.entrySet().forEach(method_entry -> {
                method_entry.getValue().getAsJsonArray().forEach(info -> {
                    JsonObject method_info = info.getAsJsonObject();
                    String method_sig = method_info.get("signature").getAsString();
                    int start = method_info.get("start_line").getAsInt();
                    int end = method_info.get("end_line").getAsInt();
                    JsonArray call_func = method_info.get("call_methods").getAsJsonArray();
                    JsonArray call_field = method_info.get("external_fields").getAsJsonArray();
                    String[] call_func_str = new String[call_func.size()];
                    String[] call_field_str = new String[call_field.size()];
                    for (int i = 0; i < call_func.size(); i++) {
                        call_func_str[i] = call_func.get(i).getAsJsonObject().get("signature").getAsString();
                    }
                    for (int i = 0; i < call_field.size(); i++) {
                        call_field_str[i] = call_field.get(i).getAsJsonObject().get("name").getAsString();
                    }
                    addDocument(class_fqn, method_sig, file, start, end, call_func_str, call_field_str);
                });
            });
        }
        return;
    }

    /**
     * Add text document to index
     * document format:
     * @param class_fqn: class fully qualified name
     * @param func_sig function signature
     * @param file file path of source code
     * @param start position of the function
     * @param end position of the function
     * @param call_func call function
     * @param call_field call field
     */
    protected void addDocument(String class_fqn, String func_sig, String file, int start, int end, String[] call_func, String[] call_field) {
        Document document = new Document();
        
        // Add non-tokenized field (for exact match)
        document.add(new StoredField("class_fqn", class_fqn));
        document.add(new StoredField("signature", func_sig));
        document.add(new StoredField("file", file));
        document.add(new StoredField("start", start));
        document.add(new StoredField("end", end));
        for(String func : call_func){
            document.add(new StringField("cfuncs", func, Field.Store.YES));
            document.add(new SortedSetDocValuesField("cfunc_dv", new BytesRef(func)));
        }
        for(String field : call_field){
            document.add(new StringField("cfields", field, Field.Store.YES));
            document.add(new SortedSetDocValuesField("cfield_dv", new BytesRef(field)));
        }

        try {
            index_writer.addDocument(document);
        } catch (IOException e) {
            System.out.println("Failed to add document: " + file + "#" + func_sig);
            System.out.println(e.getMessage());
        }
        return;
    }

    /**
     * Commit changes and close the index writer and directory
     * @throws IOException If an error occurs during commit or closing
     */
    public void close() throws IOException {
        if (index_writer != null) {
            index_writer.commit();
            index_writer.close();
        }
        if (directory != null) {
            directory.close();
        }
    }

    public void startSingle(Path code, Path index) {
        this.analyzer = new StandardAnalyzer();
        IndexWriterConfig config = new IndexWriterConfig(analyzer);
        config.setOpenMode(OpenMode.CREATE);
        try {
            if (!Files.exists(index_path)) Files.createDirectories(index);
            this.directory = FSDirectory.open(index);
            this.index_writer = new IndexWriter(directory, config);
            ParseSourceCodeInfo(code);
            close();
        } catch (IOException e) {
            System.out.println("Failed while start index: " + index);
            System.out.println(e.getMessage());
        }
        return;
    }

    public void startGroup() {
        try {
            Files.list(code_info_path).forEach(file_path -> {
                String file_name = file_path.getFileName().toString();
                if (file_name.endsWith(".json")) {
                    String project_name = file_name.split("\\.")[0];
                    System.out.println("Processing file: " + file_path.toString() + ", project: " + project_name);
                    startSingle(file_path, index_path.resolve(project_name));
                }
            });
        } catch (IOException e) {
            System.out.println("Failed to list directory: " + code_info_path);
        }
    }
    
    /**
     * Get the number of indexed documents
     */
    public int getDocumentCount() {
        return index_writer.getDocStats().numDocs;
    }

    /**
     * load data from json file
     */
    protected JsonElement loadJson(Path filePath) throws IOException, FileNotFoundException {
        InputStreamReader reader = new InputStreamReader(new FileInputStream(filePath.toFile()), "UTF-8");
        JsonElement result = new Gson().fromJson(reader, JsonElement.class);
        return result;
    }
}