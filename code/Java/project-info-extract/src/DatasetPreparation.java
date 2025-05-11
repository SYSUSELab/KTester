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

import extractor.JavaParserExtractor;

import com.google.gson.JsonElement;

/**
 * DatasetPreparation
 * @deprecated use DatasetPrepare instead
 */
@Deprecated
public class DatasetPreparation {
    static Map<String, Integer> idSet = new HashMap<String, Integer>();
    static Map<String, Integer> classSet = new HashMap<>();
    static JavaParserExtractor extractor = new JavaParserExtractor();
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
    private static String getInnerClassCode(ClassOrInterfaceDeclaration class_dec){
        // get class info: package, import, class_name, fields, method_sig
        return "";
    }
    private static String[] getClassCode(CompilationUnit cu, String class_fqn, String method_name) {
        String packageName = cu.getPackageDeclaration().map(pd -> pd.toString().trim()).orElse("");
        List<String> imports = extractor.getImports(cu);
        String class_declaration = "";
        List<String> fields = new ArrayList<>();
        List<String> method_sigs = new ArrayList<>();
        List<String> inner_class = new ArrayList<>();
        // MethodDeclaration fmethod = null;
        String class_info = "";
        String method_body = "";
        
        for (ClassOrInterfaceDeclaration class_dec: cu.findAll(ClassOrInterfaceDeclaration.class)) {
            String full_name = class_dec.getFullyQualifiedName().map(fn -> fn)
                    .orElse(packageName + "." + class_dec.getNameAsString());
            if (full_name.equals(class_fqn)) {
                // get class info: package, import, class_name, fields, method_sig
                class_dec.removeJavaDocComment();
                class_declaration = class_dec.toString().split("\\{")[0].trim();
                for( FieldDeclaration field : class_dec.getFields() ) {
                    if(field.isPublic()){
                        while(field.removeJavaDocComment()){;}
                        fields.add(field.toString());
                    }
                }
                
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
                    method.getAnnotations();
                    if (method.isPrivate()){
                        if (decl.contains(method_name) && method_name.startsWith(method.getNameAsString())) {
                            System.out.println("error: private method " + method_name + "in class " + class_fqn +" is not allowed.");
                            return null;
                        }
                    } else {
                        method_sigs.add(decl);
                        if (decl.contains(method_name) && method_name.startsWith(method.getNameAsString())) {
                            method_body = method.getDeclarationAsString() + method.getBody().map(mb -> mb.toString()).orElse("");
                        }
                    }
                }
                
            } else if (full_name.startsWith(class_fqn)){
                inner_class.add(getInnerClassCode(class_dec));
            }
        };
        class_info = packageName + "\n"
                + String.join("\n", imports)+ "\n" 
                + class_declaration + " {\n    " 
                + String.join("\n    ", fields) + "\n    " 
                + String.join(";\n    ", method_sigs) + ";\n}";
        // System.out.println("class_info: " + class_info);
        // System.out.println("method_body: " + method_body);
        return new String[] {method_body, class_info};
    }

    private static JsonObject getMethodInfo(String project_url, String method_full_name) {
        String[] presplit = method_full_name.split("\\(");
        String[] firstPart = presplit[0].split("\\.");
        firstPart[firstPart.length - 1] = firstPart[firstPart.length - 1] + "(" + presplit[1];
        String[] msplit = firstPart;
        int mlength = msplit.length;
        String method_name = msplit[mlength - 1];
        String class_name = String.join(".", Arrays.copyOfRange(msplit, 0, mlength-1));
        
        String test_id = msplit[mlength - 2] + "_" + method_name.split("\\(")[0];
        if (idSet.containsKey(test_id)) {
            int count = idSet.get(test_id);
            test_id = test_id + "_" + count;
            idSet.put(test_id, count+1);
        } else {
            idSet.put(test_id, 2);
        }
        String package_name = String.join(".", Arrays.copyOfRange(msplit, 0, mlength-2));
        String test_class = package_name + "." + test_id + "_Test";
        String sourcePath = "src/main/java/" + class_name.replace(".", "/") + ".java";
        String testPath = "src/test/java/" + test_class.replace(".", "/") + ".java";
        
        JsonObject methodInfo = new JsonObject();
        methodInfo.addProperty("id", test_id);
        methodInfo.addProperty("package", package_name);
        methodInfo.addProperty("class", class_name);
        methodInfo.addProperty("test-class", test_class);
        methodInfo.addProperty("method-name", method_name);
        methodInfo.addProperty("source-path", sourcePath);
        methodInfo.addProperty("test-path", testPath);

        // get function body
        // get class info: package, import, class_name, fields, method_sig
        // String simple = msplit[mlength-2];
        try {
            Path class_path = Paths.get(dataset_dir + "/" + project_url + "/" + sourcePath);
            CompilationUnit cu = extractor.parseJavaFile(class_path);
            String[] info = getClassCode(cu, class_name, method_name);
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