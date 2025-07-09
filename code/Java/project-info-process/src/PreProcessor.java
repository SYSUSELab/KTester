import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;

import codegraph.ControlFlowGraphBuilder;
import extractor.CodeInfoExtractor;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public class PreProcessor {
    public static void main(String[] args) {
        int arg_len = args.length;
        if (arg_len < 1) {
            throw new IllegalArgumentException("missing argument: dataset root");
        }
        if (arg_len < 2) {
            throw new IllegalArgumentException("missing argument: output dictory");
        }
        Path dataset_root = Paths.get(args[0]);
        Path output_dir = Paths.get(args[1]);
        if (!Files.exists(output_dir)) {
            try {
                Files.createDirectories(output_dir); 
            } catch (IOException e) {
                System.out.println("Failed to create output directory: " + output_dir);
                System.out.println(e.getMessage());
                System.exit(1);
            }
        }
        // process each project in dataset_root
        PreProcessor preProcessor = new PreProcessor(output_dir);
        try {
            preProcessor.processProject(dataset_root);
        } catch (IOException e) {
            System.out.println("Error: "+e.getMessage());
        }
    }

    Gson gson;
    Path output_dir;

    public PreProcessor(Path output_dir) {
        gson = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();
        this.output_dir = output_dir;
    }

    public void processProject(Path dataset_root) throws IOException{
        long start = System.currentTimeMillis();
        Files.list(dataset_root).filter(Files::isDirectory).forEach(project_dir -> {
            String project_name = project_dir.getFileName().toString();
            Path projectDir = project_dir;
            if (project_name.equals("gson")) 
                projectDir = project_dir.resolve("gson");
            Path json_path = output_dir.resolve("json/" + project_name + ".json");
            Path cfg_path = output_dir.resolve("codegraph/" + project_name + "_controlflow.json");
            System.out.println("process project: " + project_name);
            extractProjectStructure(project_name, projectDir, json_path);
            // buildControlflowFlowGraph(projectDir, cfg_path);
        });
        long end = System.currentTimeMillis();
        System.out.println("Time Cost:" + (end - start) + "ms");
    }

    private void extractProjectStructure(String projectName, Path projectDir, Path json_path){
        JsonObject projectJson = new JsonObject();
        projectJson.addProperty("project", projectName);

        Path source_folder = projectDir.resolve("src/main/java");
        Path test_folder = projectDir.resolve("src/test-original/java");
        Path jar_folder = projectDir.resolve("libs");

        CodeInfoExtractor codeInfoExtractor = new CodeInfoExtractor();
        try{
            JsonObject[] codeInfo = codeInfoExtractor.processProject(source_folder, test_folder, jar_folder);
            projectJson.add("source", codeInfo[0]);
            projectJson.add("test", codeInfo[1]);
            projectJson.add("import_dict", codeInfo[2]);
        } catch (IOException e) {
            System.out.println("Error: " + e.getMessage());
        }

        try{
            Files.writeString(json_path, gson.toJson(projectJson));
        } catch (IOException e) {
            System.out.println("Error: "+e.getMessage());
        }
        return;
    }

    private void buildControlflowFlowGraph(Path project_dir, Path cfg_path){
        String source_path = project_dir.resolve("src/main/java").toString();
        ControlFlowGraphBuilder cfgBuilder = new ControlFlowGraphBuilder(source_path);
        JsonObject graph_data = cfgBuilder.buildGraph4Project();
        try{
            Files.writeString(cfg_path, gson.toJson(graph_data));
        } catch (IOException e) {
            System.out.println("Error: "+e.getMessage());
        }
    }
}
