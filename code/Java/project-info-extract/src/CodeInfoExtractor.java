import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.FieldAccessExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JarTypeSolver;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonArray;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Dictionary;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import infostructure.*;

public class CodeInfoExtractor extends JavaExtractor {
    Gson gson;
    // List<String> imports;
    String full_class_name;
    Dictionary<String, String> depend_type;

    CodeInfoExtractor() {
        super();
        this.gson = new Gson();
        // this.imports = new ArrayList<String>();
    }

    private JsonObject extractMethodInfo(MethodDeclaration method) {
        String signature = method.getDeclarationAsString(true, false, false);
        // String body = method.getDeclarationAsString() + "\n" + method.getBody().get().toString();
        List<VariableInfo> parameters = new ArrayList<VariableInfo>();
        method.getParameters().forEach(param -> {
            String paramName = param.getNameAsString();
            String paramType = resolveType(param.getType());
            VariableInfo param_info = new VariableInfo(paramName, paramType);
            parameters.add(param_info);
        });
        // get method call
        List<MethodCallExpr> methodCalls = method.findAll(MethodCallExpr.class);
        Set<CallMethodInfo> method_call_list = new HashSet<CallMethodInfo>();
        for (MethodCallExpr methodCall : methodCalls) {
            CallMethodInfo method_call_info = resolveQualifiedName(methodCall);
            if (!method_call_info.getSignature().startsWith(full_class_name)) {
                method_call_list.add(method_call_info);
            }
        }
        // get external fields
        Set<VariableInfo> external_fields = new HashSet<VariableInfo>();
        method.findAll(FieldAccessExpr.class).forEach(fieldAccess -> {
            String fieldName = fieldAccess.getNameAsString();
            String fieldType = resolveType(fieldAccess, fieldName);
            VariableInfo field_info = new VariableInfo(fieldName, fieldType);
            external_fields.add(field_info);
        });
        // get return type
        String return_type = resolveType(method.getType());
        JsonObject method_info = this.gson.toJsonTree(
                new MethodInfo(signature, parameters, method_call_list.toArray(new CallMethodInfo[0]), external_fields.toArray(new VariableInfo[0]), return_type)
            ).getAsJsonObject();
        String methoddoc = extractJavadoc(method);
        if (methoddoc != null)
            method_info.addProperty("javadoc", methoddoc);
        return method_info;
    }

    private JsonObject extractClassInfo(ClassOrInterfaceDeclaration class_dec) {
        JsonObject classInfo = new JsonObject();
        // get field information
        List<FieldDeclaration> fields = class_dec.getFields();
        JsonArray field_list = new JsonArray();
        for (FieldDeclaration field : fields) {
            String fieldName = field.getVariable(0).getNameAsString();
            String fieldType = resolveType(field.getElementType());
            VariableInfo field_info = new VariableInfo(fieldName, fieldType);
            field_list.add(this.gson.toJsonTree(field_info));
        }
        classInfo.add("fields", field_list);

        // get constructor information
        List<ConstructorDeclaration> constructors = class_dec.getConstructors();
        JsonArray constructor_list = new JsonArray();
        for (ConstructorDeclaration constructor : constructors) {
            String signature = constructor.getSignature().toString();
            String body = constructor.getDeclarationAsString() + "\n" + constructor.getBody().toString();
            List<VariableInfo> parameters = new ArrayList<VariableInfo>();
            constructor.getParameters().forEach(param -> {
                String paramName = param.getNameAsString();
                String paramType = resolveType(param.getType());
                VariableInfo param_info = new VariableInfo(paramName, paramType);
                parameters.add(param_info);
            });
            JsonObject constructor_info = this.gson.toJsonTree(new ConstructorInfo(signature, parameters, body))
                    .getAsJsonObject();
            String methoddoc = extractJavadoc(constructor);
            if (methoddoc != null)
                constructor_info.addProperty("javadoc", methoddoc);
            constructor_list.add(constructor_info);
        }
        classInfo.add("constructors", constructor_list);

        // get method information
        List<MethodDeclaration> method_nodes = class_dec.getMethods();
        JsonObject method_list = new JsonObject();
        for (MethodDeclaration method : method_nodes) {
            String method_name = method.getNameAsString();
            JsonObject method_info = extractMethodInfo(method);
            if (method_list.has(method_name)) {
                method_list.get(method_name).getAsJsonArray().add(this.gson.toJsonTree(method_info));
            } else {
                JsonArray method_info_list = new JsonArray();
                method_info_list.add(this.gson.toJsonTree(method_info));
                method_list.add(method_name, method_info_list);
            }
        }
        classInfo.add("methods", method_list);

        return classInfo;
    }

    public JsonObject extractCodeInfo(Path javaFile) throws IOException {
        CompilationUnit cu = parseJavaFile(javaFile);
        if (cu == null)
            return null;
        // get class information
        JsonObject codeInfo = new JsonObject();
        String package_name = cu.getPackageDeclaration().map(pd -> pd.getNameAsString() + ".").orElse("");
        // // get imports
        // imports = getImports(cu);
        // for (String imp : imports) {
        // // depend_type.put(imp, imp);
        // }
        for (ClassOrInterfaceDeclaration classDecl : cu.findAll(ClassOrInterfaceDeclaration.class)) {
            String simple_name = classDecl.getNameAsString();
            full_class_name = classDecl.getFullyQualifiedName().map(fn -> fn)
                    .orElse(package_name + "." + simple_name);
            // depend_type.put(simple_name, full_class_name);
            JsonObject class_info = extractClassInfo(classDecl);
            class_info.addProperty("is_interface", classDecl.isInterface());
            String javadoc = extractJavadoc(classDecl);
            if (javadoc != null)
                class_info.addProperty("javadoc", javadoc);
            codeInfo.add(full_class_name, class_info);
        }
        return codeInfo;
    }

    public JsonObject[] processProject(Path source_dir, Path test_dir, Path jar_folder) throws IOException {
        // set type solver
        JavaParserTypeSolver source_solver = new JavaParserTypeSolver(source_dir);
        addTypeSolver(source_solver);
        Files.walk(jar_folder)
                .filter(Files::isRegularFile)
                .filter(JavaExtractor::isJarFile).forEach(file -> {
                    try {
                        JarTypeSolver jarTypeSolver = new JarTypeSolver(file);
                        addTypeSolver(jarTypeSolver);
                    } catch (IOException e) {
                        System.out.println("Error: " + e.getMessage());
                    }
                });
        // get information from source files
        JsonObject source_json = new JsonObject();
        Files.walk(source_dir)
                .filter(Files::isRegularFile)
                .filter(JavaExtractor::isJavaFile).forEach(file -> {
                    if (isJavaFile(file)) {
                        try {
                            JsonObject classInfo = extractCodeInfo(file);
                            if (classInfo != null) {
                                classInfo.entrySet()
                                        .forEach(entry -> source_json.add(entry.getKey(), entry.getValue()));
                            }
                        } catch (IOException e) {
                            System.out.println("Error: " + e.getMessage());
                        }
                    }
                });
        // get information from test files
        JsonObject test_json = new JsonObject();
        if (Files.exists(test_dir)) {
            JavaParserTypeSolver test_solver = new JavaParserTypeSolver(test_dir);
            addTypeSolver(test_solver);
            Files.walk(test_dir)
                .filter(Files::isRegularFile)
                .filter(JavaExtractor::isJavaFile).forEach(file -> {
                    try {
                        JsonObject classInfo = extractCodeInfo(file);
                        if (classInfo != null) {
                            classInfo.entrySet().forEach(entry -> test_json.add(entry.getKey(), entry.getValue()));
                        }
                    } catch (IOException e) {
                        System.out.println("Error: " + e.getMessage());
                    }
                });
        }

        return new JsonObject[] { source_json, test_json };
    }
}
