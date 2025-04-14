import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.google.gson.JsonElement;
public class DatasetPreparation {
    static Map<String, Integer> idSet = new HashMap<String, Integer>();;
    static Map<String, Integer> classSet = new HashMap<>();
    static JavaExtractor extractor = new JavaExtractor();
    static String dataset_dir;

    public static void main(String[] args) {
        if (args.length < 1) {
            System.out.println("Usage: java DatasetPreparation <dataset_dir>");
            return;
        }
        try {
            dataset_dir = args[0];
            String meta_file = dataset_dir + "/dataset_meta.json";
            String output_file = dataset_dir + "/dataset_info.json";
            prepareDataset(dataset_dir, meta_file, output_file);
            System.out.println("Dataset preparation completed successfully.");
        } catch (IOException e) {
            System.err.println("Error preparing dataset: " + e.getMessage());
            e.printStackTrace();
        }
    }
    private static String[] getClassInfo(CompilationUnit cu, String class_name, String method_name) {        
        
        List<String> imports = extractor.getImports(cu);
        String packageName = cu.getPackageDeclaration().map(pd -> pd.toString().trim()).orElse("");
        for (ClassOrInterfaceDeclaration class_dec: cu.findAll(ClassOrInterfaceDeclaration.class)) {
            if (class_dec.getNameAsString().equals(class_name)) {
                // get class info: package, import, class_name, fields, method_sig
                String method_body = "";
                class_dec.removeJavaDocComment();
                String declaration = class_dec.toString().split("\\{")[0].trim();
                List<String> fields = new ArrayList<>();
                for( FieldDeclaration field : class_dec.getFields() ) {
                    if (!field.isPrivate()){
                        while(field.removeJavaDocComment()){;}
                        fields.add(field.toString()); 
                    }
                }
                List<String> method_sigs = new ArrayList<>();
                for(ConstructorDeclaration constructor : class_dec.getConstructors()) {
                    String decl = constructor.getDeclarationAsString();
                    method_sigs.add(decl);
                    String sig = constructor.getSignature().toString();
                    if (sig.contains(method_name)) {
                        method_body = constructor.getBody().toString();
                    }
                }
                for (MethodDeclaration method : class_dec.getMethods()){
                    String decl = method.getDeclarationAsString(true, true, false);
                    if (method.isPrivate()){
                        if (decl.contains(method_name)) {
                            System.out.println("error: private method " + method_name + "in class " + class_name +" is not allowed.");
                            return null;
                        }
                    } else {
                        method_sigs.add(decl);
                        if (decl.contains(method_name)) {
                            method_body = method.getDeclarationAsString() + method.getBody().map(mb -> mb.toString()).orElse("");
                        }
                    }
                }
                String class_info = packageName + "\n"
                    + String.join("\n", imports)+ "\n" 
                    + declaration + " {\n    " 
                    + String.join("\n    ", fields) + "\n    " 
                    + String.join(";\n    ", method_sigs) + "\n}";
                // System.out.println("class_info: " + class_info);
                // System.out.println("method_body: " + method_body);
                return new String[] {method_body, class_info};
            }
        };
        return new String[] {"", ""};
    }

    private static JsonObject getMethodInfo(String project_url, String method_full_name) {
        String[] presplit = method_full_name.split("\\(");
        String[] firstPart = presplit[0].split("\\.");
        firstPart[firstPart.length - 1] = firstPart[firstPart.length - 1] + "(" + presplit[1];
        String[] msplit = firstPart;
        int mlength = msplit.length;
        String method_name = msplit[mlength - 1];
        String className = String.join(".", Arrays.copyOfRange(msplit, 0, mlength-1));
        
        String testId = msplit[mlength - 2] + "_" + method_name.split("\\(")[0];
        if (idSet.containsKey(testId)) {
            int count = idSet.get(testId);
            testId = testId + "_" + count;
            idSet.put(testId, count+1);
        } else {
            idSet.put(testId, 2);
        }
        String packageName = String.join(".", Arrays.copyOfRange(msplit, 0, mlength-2));
        String testClass = packageName + "." + testId + "_Test";
        String sourcePath = "src/main/java/" + className.replace(".", "/") + ".java";
        String testPath = "src/test/java/" + testClass.replace(".", "/") + ".java";
        
        JsonObject methodInfo = new JsonObject();
        methodInfo.addProperty("id", testId);
        methodInfo.addProperty("package", packageName);
        methodInfo.addProperty("class", className);
        methodInfo.addProperty("test-class", testClass);
        methodInfo.addProperty("method-name", method_name);
        methodInfo.addProperty("source-path", sourcePath);
        methodInfo.addProperty("test-path", testPath);

        // get function body
        // get class info: package, import, class_name, fields, method_sig
        String simple = msplit[mlength-2];
        try {
            Path class_path = Paths.get(dataset_dir + "/" + project_url + "/" + sourcePath);
            CompilationUnit cu = extractor.parseJavaFile(class_path);
            String[] info = getClassInfo(cu, simple, method_name);
            if(info==null) return null;
            methodInfo.addProperty("focused-method", info[0]);
            methodInfo.addProperty("class-info", info[1]);
        } catch (Exception e) {
            System.out.println("Error while parsing file: "+e.getMessage());
            methodInfo.addProperty("focused-method", "");
            methodInfo.addProperty("class-info", "");        }
        return methodInfo;
    }

    public static void prepareDataset(String dataset_dir, String meta_file, String output_file) throws IOException {
        JsonArray metaData = loadJson(meta_file).getAsJsonArray();
        JsonObject datasetInfo = new JsonObject();
        
        for (int i = 0; i < metaData.size(); i++) {
            JsonObject mdata = metaData.get(i).getAsJsonObject();
            JsonObject projectInfo = new JsonObject();
            String projectName = mdata.get("project_name").getAsString();
            String projectUrl = mdata.get("put_path").getAsString().replace("/root/experiments/puts/", "");
            projectInfo.addProperty("project-name", projectName);
            projectInfo.addProperty("project-url", projectUrl);
            // get focused methods
            JsonArray focused_methods = new JsonArray();
            idSet.clear();
            classSet.clear();
            
            JsonObject methodsObj = mdata.getAsJsonObject("method_name_to_idx");
            for (Map.Entry<String, JsonElement> entry : methodsObj.entrySet()) {
                String methodNameToIdx = entry.getKey();
                JsonObject methodInfo = getMethodInfo(projectUrl, methodNameToIdx);
                if (methodInfo == null) continue;
                focused_methods.add(methodInfo);
            }
            
            projectInfo.add("focused-methods", focused_methods);
            datasetInfo.add(projectName, projectInfo);
        }

        String outputFile = Paths.get(output_file).toString();
        writeJson(outputFile, datasetInfo);
    }

    /**
     * load data from json file
     */
    public static JsonElement loadJson(String filePath) throws IOException {
        try (FileReader reader = new FileReader(filePath)) {
            return new Gson().fromJson(reader, JsonElement.class);
        }
    }
    
    /**
     * write data to json file
     */
    public static void writeJson(String filePath, JsonElement jsonElement) throws IOException {
        try (FileWriter writer = new FileWriter(filePath)) {
            Gson gson = new GsonBuilder()
                    .setPrettyPrinting()
                    .disableHtmlEscaping()
                    .create();
            writer.write(gson.toJson(jsonElement));
        }
    }
}