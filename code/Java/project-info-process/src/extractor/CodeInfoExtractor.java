package extractor;

import com.github.javaparser.ast.AccessSpecifier;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.EnumConstantDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.FieldAccessExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.NameExpr;
import com.github.javaparser.ast.expr.ObjectCreationExpr;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JavaParserTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.JarTypeSolver;
import com.google.gson.Gson;
import com.google.gson.JsonObject;
import com.google.gson.JsonArray;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import infostructure.*;

public class CodeInfoExtractor extends JavaParserExtractor implements BaseImportDict {
    Gson gson;
    String full_class_name;

    public CodeInfoExtractor() {
        super();
        this.gson = new Gson();
        initImportDict();
    }

    private JsonObject extractConstuctorInfo(ConstructorDeclaration constructor) {
        // get start and end line
        int[] position = getPosition(constructor);
        // get method signature
        String signature = constructor.getSignature().toString();
        signature = signature.replaceAll("\\.\\.\\.", "[]");
        // String body = constructor.getDeclarationAsString() + "\n" +
        // constructor.getBody().toString();
        List<VariableInfo> parameters = new ArrayList<VariableInfo>();
        constructor.getParameters().forEach(param -> {
            String paramName = param.getNameAsString();
            String paramType = resolveType(param.getType());
            VariableInfo param_info = new VariableInfo(paramName, paramType);
            parameters.add(param_info);
        });
        // get method call
        List<MethodCallExpr> methodCalls = constructor.findAll(MethodCallExpr.class);
        HashMap<CallMethodInfo, Set<Integer>> method_call_list = new HashMap<CallMethodInfo, Set<Integer>>();
        for (MethodCallExpr methodCall : methodCalls) {
            CallMethodInfo method_call_info = resolveQualifiedName(methodCall);
            // if (!method_call_info.getSignature().startsWith(full_class_name)) {
            // method_call_list.add(method_call_info);
            int[] call_pos = getPosition(methodCall);
            if (method_call_list.get(method_call_info) == null) {
                Set<Integer> line_numbers = new HashSet<Integer>();
                line_numbers.add(call_pos[0]);
                method_call_list.put(method_call_info, line_numbers);
            } else {
                Set<Integer> line_numbers = method_call_list.get(method_call_info);
                line_numbers.add(call_pos[0]);
            }
            // }
        }
        for (CallMethodInfo method_call_info : method_call_list.keySet()) {
            Set<Integer> line_numbers = method_call_list.get(method_call_info);
            int[] intArray = line_numbers.stream().mapToInt(Integer::intValue).toArray();
            method_call_info.setLineNumbers(intArray);
        }
        // get external fields
        Set<VariableInfo> external_fields = new HashSet<VariableInfo>();
        constructor.findAll(FieldAccessExpr.class).forEach(fieldAccess -> {
            VariableInfo field_info = resolveQualifiedName(fieldAccess);
            external_fields.add(field_info);
        });

        AccessSpecifier access_type = constructor.getAccessSpecifier();
        ConstructorInfo constructor_obj = new ConstructorInfo(signature,
                parameters,
                position,
                access_type,
                method_call_list.keySet().toArray(new CallMethodInfo[0]),
                external_fields.toArray(new VariableInfo[0]));
        JsonObject constructor_info = this.gson.toJsonTree(constructor_obj).getAsJsonObject();
        String methoddoc = extractJavadoc(constructor);
        if (methoddoc != null)
            constructor_info.addProperty("javadoc", methoddoc);
        return constructor_info;
    }

    private JsonObject extractMethodInfo(MethodDeclaration method) {
        // get start and end line
        int[] position = getPosition(method);
        // get method signature
        String signature = method.getDeclarationAsString(true, false, false);
        signature = signature.replaceAll("\\.\\.\\.", "[]");
        // String body = method.getDeclarationAsString() + "\n" +
        // method.getBody().get().toString();
        List<VariableInfo> parameters = new ArrayList<VariableInfo>();
        method.getParameters().forEach(param -> {
            String paramName = param.getNameAsString();
            String paramType = resolveType(param.getType());
            VariableInfo param_info = new VariableInfo(paramName, paramType);
            parameters.add(param_info);
        });
        // get method call
        List<MethodCallExpr> methodCalls = method.findAll(MethodCallExpr.class);
        HashMap<CallMethodInfo, Set<Integer>> method_call_list = new HashMap<CallMethodInfo, Set<Integer>>();
        for (MethodCallExpr methodCall : methodCalls) {
            CallMethodInfo method_call_info = resolveQualifiedName(methodCall);
            // if (!method_call_info.getSignature().startsWith(full_class_name)) {
            int[] call_pos = getPosition(methodCall);
            if (method_call_list.get(method_call_info) == null) {
                Set<Integer> line_numbers = new HashSet<Integer>();
                line_numbers.add(call_pos[0]);
                method_call_list.put(method_call_info, line_numbers);
            } else {
                Set<Integer> line_numbers = method_call_list.get(method_call_info);
                line_numbers.add(call_pos[0]);
            }
            // }
        }
        List<ObjectCreationExpr> object_creations = method.findAll(ObjectCreationExpr.class);
        for (ObjectCreationExpr objectCreation : object_creations) {
            CallMethodInfo method_call_info = resolveQualifiedName(objectCreation);
            // if (!method_call_info.getSignature().startsWith(full_class_name)) {
            // method_call_list.add(method_call_info);
            int[] call_pos = getPosition(objectCreation);
            if (method_call_list.get(method_call_info) == null) {
                Set<Integer> line_numbers = new HashSet<Integer>();
                line_numbers.add(call_pos[0]);
                method_call_list.put(method_call_info, line_numbers);
            } else {
                Set<Integer> line_numbers = method_call_list.get(method_call_info);
                line_numbers.add(call_pos[0]);
            }
            // }
        }
        for (CallMethodInfo method_call_info : method_call_list.keySet()) {
            Set<Integer> line_numbers = method_call_list.get(method_call_info);
            int[] intArray = line_numbers.stream().mapToInt(Integer::intValue).toArray();
            method_call_info.setLineNumbers(intArray);
        }
        // get external fields
        Set<VariableInfo> external_fields = new HashSet<VariableInfo>();
        method.findAll(FieldAccessExpr.class).forEach(fieldAccess -> {
            VariableInfo field_info = resolveQualifiedName(fieldAccess);
            external_fields.add(field_info);
        });
        method.findAll(NameExpr.class).forEach(nameExpr -> {
            VariableInfo field_info = resolveQualifiedName(nameExpr);
            if (field_info != null) {
                external_fields.add(field_info);
            }
        });
        // get return type
        String return_type = resolveType(method.getType());
        // get access type
        AccessSpecifier access_type = method.getAccessSpecifier();
        MethodInfo method_obj = new MethodInfo(signature,
                parameters,
                position,
                access_type,
                method_call_list.keySet().toArray(new CallMethodInfo[0]),
                external_fields.toArray(new VariableInfo[0]),
                return_type);
        JsonObject method_info = this.gson.toJsonTree(method_obj).getAsJsonObject();
        String methoddoc = extractJavadoc(method);
        if (methoddoc != null)
            method_info.addProperty("javadoc", methoddoc);
        return method_info;
    }

    private JsonObject extractClassInfo(ClassOrInterfaceDeclaration class_dec) {
        JsonObject class_info = new JsonObject();
        class_info.addProperty("is_abstract", class_dec.isAbstract());

        // get constructor information
        List<ConstructorDeclaration> constructors = class_dec.getConstructors();
        JsonArray constructor_list = new JsonArray();
        for (ConstructorDeclaration constructor : constructors) {
            if (constructor.getAnnotationByClass(Deprecated.class).isPresent())
                // || constructor.isPrivate())
                continue;
            JsonObject constructor_info = extractConstuctorInfo(constructor);
            constructor_list.add(constructor_info);
        }
        class_info.add("constructors", constructor_list);

        // get field information
        List<FieldDeclaration> fields = class_dec.getFields();
        JsonArray field_list = new JsonArray();
        for (FieldDeclaration field : fields) {
            if (field.getAnnotationByClass(Deprecated.class).isPresent())
                continue;
            String fieldName = field.getVariable(0).getNameAsString();
            String fieldType = resolveType(field.getElementType());
            int position[] = getPosition(field);
            FieldInfo field_info = new FieldInfo(fieldName, fieldType, position);
            field_info.equals(field_info);
            field_list.add(this.gson.toJsonTree(field_info));
        }
        class_info.add("fields", field_list);

        // get method information
        List<MethodDeclaration> method_nodes = class_dec.getMethods();
        JsonObject method_list = new JsonObject();
        for (MethodDeclaration method : method_nodes) {
            if (method.getAnnotationByClass(Deprecated.class).isPresent())
                continue;
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
        class_info.add("methods", method_list);

        return class_info;
    }

    public JsonObject extractEnumInfo(EnumDeclaration enum_decl) {
        JsonObject enum_info = new JsonObject();
        // get enum constant
        List<EnumConstantDeclaration> enum_constants = enum_decl.getEntries();
        JsonArray constant_list = new JsonArray();
        for (EnumConstantDeclaration constant : enum_constants) {
            String constant_name = constant.getNameAsString();
            int position[] = getPosition(constant);
            EnumConstantInfo enumConstantInfo = new EnumConstantInfo(constant_name, position);
            constant_list.add(this.gson.toJsonTree(enumConstantInfo));
        }
        enum_info.add("constants", constant_list);
        // get field information
        List<FieldDeclaration> fields = enum_decl.getFields();
        JsonArray field_list = new JsonArray();
        for (FieldDeclaration field : fields) {
            String fieldName = field.getVariable(0).getNameAsString();
            String fieldType = resolveType(field.getElementType());
            int position[] = getPosition(field);
            FieldInfo field_info = new FieldInfo(fieldName, fieldType, position);
            field_info.equals(field_info);
            field_list.add(this.gson.toJsonTree(field_info));
        }
        enum_info.add("fields", field_list);

        // get constructor information
        List<ConstructorDeclaration> constructors = enum_decl.getConstructors();
        JsonArray constructor_list = new JsonArray();
        for (ConstructorDeclaration constructor : constructors) {
            JsonObject constructor_info = extractConstuctorInfo(constructor);
            constructor_list.add(constructor_info);
        }
        enum_info.add("constructors", constructor_list);

        // get method information
        List<MethodDeclaration> method_nodes = enum_decl.getMethods();
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
        enum_info.add("methods", method_list);
        return enum_info;
    }

    public JsonObject extractCodeInfo(Path javaFile, Path base_path) throws IOException {
        CompilationUnit cu = parseJavaFile(javaFile);
        if (cu == null)
            return null;
        // add import dictionary
        addImportDict(cu);
        // get class information
        JsonObject codeInfo = new JsonObject();
        String package_name = cu.getPackageDeclaration().map(pd -> pd.getNameAsString()).orElse("");
        String relative_path = base_path.relativize(javaFile).toString();
        for (ClassOrInterfaceDeclaration classDecl : cu.findAll(ClassOrInterfaceDeclaration.class)) {
            if (classDecl.getAnnotationByClass(Deprecated.class).isPresent())
                continue;
            String simple_name = classDecl.getNameAsString();
            full_class_name = classDecl.getFullyQualifiedName().map(fn -> fn)
                    .orElse(package_name + "." + simple_name);
            JsonObject class_info = extractClassInfo(classDecl);
            class_info.addProperty("file", relative_path);
            String javadoc = extractJavadoc(classDecl);
            if (javadoc != null)
                class_info.addProperty("javadoc", javadoc);
            codeInfo.add(full_class_name, class_info);
        }
        for (EnumDeclaration enum_decl : cu.findAll(EnumDeclaration.class)) {
            if (enum_decl.getAnnotationByClass(Deprecated.class).isPresent())
                continue;
            String simple_name = enum_decl.getNameAsString();
            full_class_name = enum_decl.getFullyQualifiedName().map(fn -> fn)
                    .orElse(package_name + "." + simple_name);
            JsonObject enum_info = extractEnumInfo(enum_decl);
            enum_info.addProperty("file", relative_path);
            String javadoc = extractJavadoc(enum_decl);
            if (javadoc != null)
                enum_info.addProperty("javadoc", javadoc);
            codeInfo.add(full_class_name, enum_info);
        }
        return codeInfo;
    }

    public JsonObject[] processProject(Path source_dir, Path test_dir, Path jar_folder) throws IOException {
        // set type solver
        JavaParserTypeSolver source_solver = new JavaParserTypeSolver(source_dir);
        addTypeSolver(source_solver);
        Files.walk(jar_folder)
                .filter(Files::isRegularFile)
                .filter(JavaParserExtractor::isJarFile).forEach(file -> {
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
                .filter(JavaParserExtractor::isJavaFile).forEach(file -> {
                    try {
                        JsonObject classInfo = extractCodeInfo(file, source_dir);
                        if (classInfo != null) {
                            classInfo.entrySet()
                                    .forEach(entry -> source_json.add(entry.getKey(), entry.getValue()));
                        }
                    } catch (IOException e) {
                        System.out.println("Error: " + e.getMessage());
                    }
                });
        // get information from test files
        JsonObject test_json = new JsonObject();
        if (Files.exists(test_dir)) {
            JavaParserTypeSolver test_solver = new JavaParserTypeSolver(test_dir);
            addTypeSolver(test_solver);
            Files.walk(test_dir)
                    .filter(Files::isRegularFile)
                    .filter(JavaParserExtractor::isJavaFile).forEach(file -> {
                        try {
                            JsonObject classInfo = extractCodeInfo(file, test_dir);
                            if (classInfo != null) {
                                classInfo.entrySet().forEach(entry -> test_json.add(entry.getKey(), entry.getValue()));
                            }
                        } catch (IOException e) {
                            System.out.println("Error: " + e.getMessage());
                        }
                    });
        }
        // construct import dictionary
        JsonObject import_dict_json = constructImportDict();
        return new JsonObject[] { source_json, test_json, import_dict_json };
    }
}
