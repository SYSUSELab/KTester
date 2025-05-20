import org.apache.lucene.document.Document;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.index.MultiDocValues;
import org.apache.lucene.index.SortedSetDocValues;
import org.apache.lucene.search.BooleanClause;
import org.apache.lucene.search.BooleanQuery;
import org.apache.lucene.search.IndexSearcher;
import org.apache.lucene.search.Query;
import org.apache.lucene.search.ScoreDoc;
import org.apache.lucene.search.TopDocs;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.FSDirectory;
import org.apache.lucene.util.BytesRef;

import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;

import similarity.JaccardSimilarityQuery;

public class CodeSearcher {
    // private final Path project_root;
    private final Path index_path;
    // private StandardAnalyzer analyzer;
    private Directory directory;
    private IndexReader index_reader;
    private IndexSearcher index_searcher;
    private SortedSetDocValues func_dv;
    private SortedSetDocValues field_dv;
    public Set<ResultFormat> results;
    private int top_k = 10;
    private float w_c = 0.6f;
    private float w_f = 0.4f;

    public static String main(String[] args) {
        if (args.length < 3) {
            throw new IllegalArgumentException("Arguments for Code Searcher: <project_root> <index path> <query string> <top k>");
        }
        
        Path project = Path.of(args[0]);
        Path index = Path.of(args[1]);
        String query_string = args[2];
        

        if (!Files.isDirectory(project)){
            throw new IllegalArgumentException("project root should be a directory!");
        }
        if (!Files.exists(index)) {
            throw new IllegalArgumentException("index_path should be a directory!");
        }
        
        try {
            CodeSearcher searchEngine = new CodeSearcher(project, index);
            if (args.length >= 4) {
                searchEngine.setTopK(Integer.parseInt(args[3]));
            }
            List<QueryFormat> query_list = searchEngine.parseQueryString(query_string);
            for (QueryFormat query : query_list) {
                searchEngine.search(query);
            }
            searchEngine.close();
            JsonArray result_list = searchEngine.getResultList();
            return result_list.toString();
            
        } catch (Exception e) {
            System.err.println("Error occurred during search: " + e.getMessage());
            e.printStackTrace();
        }
        return "";
    }

    public CodeSearcher() {
        this.index_path = null;
    }
    
    /**
     * Initialize the search engine
     * @param indexPath Index path
     * @throws IOException If an error occurs while opening the index
     */
    public CodeSearcher(Path project, Path index) throws IOException{
        // this.project_root = project;
        this.index_path = index;
        // this.analyzer = new StandardAnalyzer();
        this.directory = FSDirectory.open(index_path);
        this.index_reader = DirectoryReader.open(directory);
        this.index_searcher = new IndexSearcher(index_reader);
        this.func_dv = MultiDocValues.getSortedSetValues(index_reader, "cfunc_dv");
        this.field_dv = MultiDocValues.getSortedSetValues(index_reader, "cfield_dv");
        setResultSet();
        // System.out.println("number of doc: "+this.index_reader.numDocs());
    }

    private void setResultSet(){
        // Results with same FQN and signature will be overwritten while keeping the higher score
        this.results = new TreeSet<ResultFormat>((a, b) -> {
            if (a.equals(b)) {
                a.related_func.addAll(b.related_func);
                b.related_func.addAll(a.related_func);
                float higher = Math.max(a.score, b.score);
                a.score = higher;
                b.score = higher;
                return 0;
            }
            // Sort scores in descending order
            return Float.compare(b.score, a.score);
        });
    }

    public void setTopK(int top_k) {
        this.top_k = top_k;
    }
    
    private class QueryFormat {
        String sig;
        String[] function;
        String[] field;
        public QueryFormat(String sig, String [] function, String [] field) {
            this.sig = sig;
            this.function = function;
            this.field = field;
        }
    }

    @SuppressWarnings("unused")
    private class ResultFormat {
        public String class_fqn;
        public String signature;
        public Set<String> related_func;
        private String file;
        private int start;
        private int end;
        public float score;
        public ResultFormat(String fqn, String sig, String relf, String file, int start, int end, float score) {
            this.class_fqn = fqn;
            this.signature = sig;
            this.related_func = new HashSet<>();
            this.related_func.add(relf);
            this.file = file;
            this.start = start;
            this.end = end;
            this.score = score;
        }
        @Override
        public boolean equals(Object obj) {
            if (this == obj) return true;
            if (obj == null || getClass() != obj.getClass()) return false;
            ResultFormat that = (ResultFormat) obj;
            boolean fqnEqual = this.class_fqn.equals(that.class_fqn);
            boolean sigEqual = this.signature.equals(that.signature);
            return fqnEqual && sigEqual;
        }

        @Override
        public int hashCode() {
            return class_fqn.hashCode() + signature.hashCode();
        }
    }
    
    /**
     * format of query string:
     * [
     *   {
     *     "sig": "xxx",
     *     "function": ["xxx","xxx"], 
     *     "field": ["xxx","xxx"],
     *   },
     *   ...
     * ]
     */
    public List<QueryFormat> parseQueryString(String query) {
        JsonArray queryArray = new Gson().fromJson(query, JsonArray.class);
        List<QueryFormat> queryList = new ArrayList<>();
        for (int i = 0; i < queryArray.size(); i++) {
            JsonObject queryObject = queryArray.get(i).getAsJsonObject();
            JsonArray functionArray = queryObject.get("function").getAsJsonArray();
            JsonArray fieldArray =  queryObject.get("field").getAsJsonArray();
            String sig = queryObject.get("sig").getAsString();
            String[] function = new String[functionArray.size()];
            String[] field = new String[fieldArray.size()];
            for (int j = 0; j < functionArray.size(); j++) {
                function[j] = functionArray.get(j).getAsString();
            }
            for (int j = 0; j < fieldArray.size(); j++) {
                field[j] = fieldArray.get(j).getAsString();
            }
            queryList.add(new QueryFormat(sig, function, field));
        }
        return queryList;    
    }

    /**
     * this method is used to get the ordinals of a term in a field
     *
     * @param reader 
     * @param dvField DocValues field name, e.g. "calls_dv"
     * @param terms   The collection of terms of query
     * @return ordinals orded by asc
     */
    private java.util.Map<String, Long> funcOrdCache = new java.util.HashMap<>();
    private java.util.Map<String, Long> fieldOrdCache = new java.util.HashMap<>();
    
    public long[] getOrds(IndexReader reader, String dv_field, String[] terms) {
        // 1) 获取合并后全局的 SortedSetDocValues
        SortedSetDocValues dv = null;
        java.util.Map<String, Long> cache = null;
        
        if (dv_field.equals("cfunc_dv")) {
            dv = this.func_dv;
            cache = this.funcOrdCache;
        } else if (dv_field.equals("cfield_dv")) {
            dv = this.field_dv;
            cache = this.fieldOrdCache;
        } else {
            return new long[0];
        }
        
        List<Long> ordList = new ArrayList<>(terms.length);
        BytesRef bytesRef = new BytesRef();
        
        for (String term : terms) {
            Long cachedOrd = cache.get(term);
            if (cachedOrd != null) {
                if (cachedOrd >= 0) {
                    ordList.add(cachedOrd);
                }
                continue;
            }
            
            try {
                // avoid creating a new BytesRef each time
                bytesRef.bytes = term.getBytes();
                bytesRef.offset = 0;
                bytesRef.length = bytesRef.bytes.length;
                
                long ord = dv.lookupTerm(bytesRef);
                // 缓存结果
                cache.put(term, ord);
                if (ord >= 0) {
                    ordList.add(ord);
                }
            } catch (IOException e) {
                cache.put(term, -1L);
                continue;
            }
        }
        
        long[] ords = new long[ordList.size()];
        int i = 0;
        for (Long ord : ordList) {
            ords[i++] = ord;
        }
        java.util.Arrays.sort(ords);
        return ords;
    }

    // public void updateResults(ResultFormat result, String call_sig) {
    //     this.results.add(result);
    // }

    public void search(QueryFormat query) throws IOException {
        // get the ords of q's calls/fields in their dv fields
        String[] qfunc = query.function;
        String[] qfield = query.field;
        long[] qcOrds = getOrds(index_searcher.getIndexReader(), "cfunc_dv", qfunc);
        long[] qfOrds = getOrds(index_searcher.getIndexReader(), "cfield_dv", qfield);

        // construct Query
        Query simCalls  = new JaccardSimilarityQuery("cfunc_dv",  qcOrds, qfunc.length, w_c);
        Query simFields = new JaccardSimilarityQuery("cfield_dv", qfOrds, qfield.length, w_f);
        BooleanQuery combined = new BooleanQuery.Builder()
            .add(simCalls, BooleanClause.Occur.SHOULD)
            .add(simFields, BooleanClause.Occur.SHOULD)
            .build();

        TopDocs results = index_searcher.search(combined, top_k);
        for (ScoreDoc sd : results.scoreDocs) {
            Document doc = index_searcher.storedFields().document(sd.doc);
            ResultFormat result = new ResultFormat(doc.get("class_fqn"), 
                        doc.get("signature"),
                        query.sig,
                        doc.get("file"), 
                        Integer.parseInt(doc.get("start")), 
                        Integer.parseInt(doc.get("end")), 
                        sd.score);
            this.results.add(result);
        }

    }

    public JsonArray getResultList() {
        // transform the result set to JsonArray and only keep the top k results
        System.out.println(this.results.size()+" results found.");
        List<ResultFormat> topResults = new ArrayList<>(this.results);
        topResults.removeIf(result -> result.score == 1);
        topResults = topResults.subList(0, Math.min(topResults.size(), this.top_k));
        JsonArray result_list = new Gson().toJsonTree(topResults).getAsJsonArray();
        return result_list;
    }
    
    /**
     * Close the index reader and directory
     * @throws IOException If an error occurs during closing
     */
    public void close() throws IOException {
        if (index_reader != null) {
            index_reader.close();
        }
        if (directory != null) {
            directory.close();
        }
    }
    
    /**
     * Get the number of documents in the index
     * @return Number of documents in the index
     */
    public int getDocumentCount() {
        return index_reader.numDocs();
    }
}