import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import extractor.SpoonExtractor;
import spoon.reflect.code.CtFieldRead;
import spoon.reflect.code.CtFieldWrite;
import spoon.reflect.code.CtInvocation;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtField;
import spoon.reflect.declaration.CtImport;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.declaration.CtType;
import spoon.reflect.reference.CtExecutableReference;
import spoon.reflect.reference.CtFieldReference;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

public class DatasetPrepare {
    Map<String, Integer> idSet = new HashMap<String, Integer>();
    SpoonExtractor extractor = new SpoonExtractor();

    public static void main(String[] args) {
        if (args.length < 1) {
            System.out.println("Usage: java DatasetPreparation <dataset_dir>");
            return;
        }
        DatasetPrepare prepare = new DatasetPrepare();
        try {
            String dataset_dir = args[0];
            String meta_file = dataset_dir + "/dataset_meta.json";
            String output_file = dataset_dir + "/dataset_info.json";
            long start = System.currentTimeMillis();
            prepare.prepareDataset(dataset_dir, meta_file, output_file);
            long end = System.currentTimeMillis();
            System.out.println("Dataset preparation completed successfully.");
            System.out.println("Time Cost:" + (end - start) + "ms");
        } catch (IOException e) {
            System.err.println("Error preparing dataset: " + e.getMessage());
            e.printStackTrace();
        }
    }

    private String[] getClassCode(String class_fqn, String method_name, String[] arguments) {
        String package_name = "";
        List<String> imports = new ArrayList<String>();
        String class_declaration = "";
        List<String> fields = new ArrayList<String>();
        List<String> method_decl = new ArrayList<String>();
        Set<String> inner_class = new HashSet<String>();
        String method_body = "";
        String class_code = "";
        
        // get class info
        CtClass<?> fcClass = extractor.getCtClass(class_fqn);
        if (fcClass != null) {
            package_name = fcClass.getPackage().toString();
            // collect imports
            for (CtImport ctImport : extractor.getImports(fcClass)) {
                imports.add(ctImport.prettyprint());
            }
            // class declaration
            extractor.removeComment(fcClass);
            class_declaration = fcClass.prettyprint().split("\\{")[0].trim();

            Set<String> calledMethods = new HashSet<>();
            Set<String> accessedFields = new HashSet<>();
            List<CtTypeReference<?>> nestedRefs = fcClass.getNestedTypes().stream()
                                                    .<CtTypeReference<?>>map(CtType::getReference)
                                                    .collect(Collectors.toList());
            // get method body
            CtMethod<?> fcMethod = extractor.getCtMethod(fcClass, method_name, arguments);
            if (fcMethod != null) {
                if (fcMethod.isPrivate()){
                    System.out.println("error: private method " + method_name + " in class " + class_fqn +" is not allowed.");
                    return null;
                }
                extractor.removeComment(fcMethod);
                method_body = fcMethod.prettyprint();
                // collect called methods
                for (CtInvocation<?> inv : fcMethod.getElements(new TypeFilter<>(CtInvocation.class))) {
                    CtExecutableReference<?> exec = inv.getExecutable();
                    CtTypeReference<?> decType = exec.getDeclaringType();
                    if (decType==null) continue;
                    if (decType.equals(fcClass.getReference())) {
                        calledMethods.add(exec.getSimpleName());
                    } else if (nestedRefs.contains(decType)) {
                        inner_class.add(fcClass.getNestedType(decType.getSimpleName()).prettyprint());
                    }
                }
                // collect accessed fields
                for (CtFieldRead<?> fr : fcMethod.getElements(new TypeFilter<>(CtFieldRead.class))) {
                    CtFieldReference<?> fref = fr.getVariable();
                    CtTypeReference<?> decType = fref.getDeclaringType();
                    if (decType==null) continue;
                    if (decType.equals(fcClass.getReference())) {
                        accessedFields.add(fref.getSimpleName());
                    } else if (nestedRefs.contains(decType)) {
                        inner_class.add(fcClass.getNestedType(decType.getSimpleName()).prettyprint());    
                    }
                }
                for (CtFieldWrite<?> fw : fcMethod.getElements(new TypeFilter<>(CtFieldWrite.class))) {
                    CtFieldReference<?> fref = fw.getVariable();
                    CtTypeReference<?> decType = fref.getDeclaringType();
                    if (decType==null) continue;
                    if (decType.equals(fcClass.getReference())) {
                        accessedFields.add(fref.getSimpleName());
                    } else if (nestedRefs.contains(decType)) {
                        inner_class.add(fcClass.getNestedType(decType.getSimpleName()).prettyprint());
                    }
                }
            }
            // collect method declaration
            for (CtMethod<?> method : fcClass.getMethods()) {
                if ((!method.isPrivate() || calledMethods.contains(method.getSimpleName()))
                && method != fcMethod
                && method.getAnnotation(Deprecated.class)==null) {
                    extractor.removeComment(method);
                    method_decl.add(method.prettyprint().split("\\{")[0].trim());
                }
            }
            // collect fields
            for (CtField<?> field : fcClass.getFields()) {
                if ((!field.isPrivate() || accessedFields.contains(field.getSimpleName()))
                && field.getAnnotation(Deprecated.class)==null) {
                    extractor.removeComment(field);
                    fields.add(field.prettyprint());
                }
            }
            // build class code
            StringBuilder sb = new StringBuilder();
            sb.append("package ").append(package_name).append(";\n");
            sb.append(String.join("\n", imports)).append("\n");                
            sb.append(class_declaration).append(" {\n    ");
            sb.append(String.join("\n    ", fields)).append("\n    ");
            for (String innerCls : inner_class) {
                sb.append("    ").append(innerCls.replace("\n", "\n    ")).append("\n");
            }
            sb.append(method_body.replace("\n", "\n    ")).append("\n");
            sb.append(String.join(";\n    ", method_decl)).append(";\n");
            sb.append("}");
            class_code = sb.toString();
        }
        return new String[] {method_body, class_code};
    }

    private JsonObject getMethodInfo(String project_url, String method_full_name) {
        String[] presplit = method_full_name.split("\\(");
        String[] firstPart = presplit[0].split("\\.");
        String[] msplit = Arrays.copyOf(firstPart, firstPart.length);
        msplit[msplit.length - 1] = firstPart[firstPart.length - 1] + "(" + presplit[1];
        int mlength = msplit.length;
        String method_name = msplit[mlength - 1];
        String class_name = String.join(".", Arrays.copyOfRange(msplit, 0, mlength-1));
       
        while (presplit[1].contains("<")) {
            presplit[1] = presplit[1].replaceAll("<[^<>]*>", "");
        }
        String[] arguments = presplit[1].split(", ");
        arguments[arguments.length-1] = arguments[arguments.length-1].replace(")", "");
        if (arguments.length == 1 && arguments[0].equals("")) {
            arguments = new String[]{};
        }
        
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
        try {
            String[] class_code = getClassCode(class_name, firstPart[mlength - 1], arguments);
            if(class_code==null) return null;
            methodInfo.addProperty("focused-method", class_code[0]);
            methodInfo.addProperty("class-code", class_code[1]);;
        } catch (Exception e) {
            System.out.println("Error while get class code: "+e.getMessage());
            methodInfo.addProperty("focused-method", "");
            methodInfo.addProperty("class-code", "");
            e.printStackTrace();
        }
        return methodInfo;
    }

    private void setProjectAnalyzer(String project_url) {
        String[] source = new String[]{
            project_url + "/src/main/java",
            // project_url+"/src/test/java"
        };
        String[] classpath = new String[]{project_url + "/libs"};
        this.extractor = new SpoonExtractor(source, classpath);
    }

    public void prepareDataset(String dataset_dir, String meta_file, String output_file) throws IOException {
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
            setProjectAnalyzer(dataset_dir + "/" + projectUrl);
            JsonArray focused_methods = new JsonArray();
            idSet.clear();
            
            JsonObject methodsObj = mdata.getAsJsonObject("method_name_to_idx");
            for (Map.Entry<String, JsonElement> entry : methodsObj.entrySet()) {
                String methodNameToIdx = entry.getKey();
                JsonObject methodInfo = getMethodInfo(projectUrl, methodNameToIdx);
                if (methodInfo == null) continue;
                focused_methods.add(methodInfo);
            }
            
            projectInfo.add("focal-methods", focused_methods);
            datasetInfo.add(projectName, projectInfo);
        }

        String outputFile = Paths.get(output_file).toString();
        writeJson(outputFile, datasetInfo);
    }
    
    /**
     * load data from json file
     */
    public JsonElement loadJson(String filePath) throws IOException {
        try (FileReader reader = new FileReader(filePath)) {
            return new Gson().fromJson(reader, JsonElement.class);
        }
    }
    
    /**
     * write data to json file
     */
    public void writeJson(String filePath, JsonElement jsonElement) throws IOException {
        try (FileWriter writer = new FileWriter(filePath)) {
            Gson gson = new GsonBuilder()
                    .setPrettyPrinting()
                    .disableHtmlEscaping()
                    .create();
            writer.write(gson.toJson(jsonElement));
        }
    }
}
