package editcode;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ParseStart;
import com.github.javaparser.Provider;
import com.github.javaparser.Providers;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.ImportDeclaration;
import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.AnnotationExpr;
import com.github.javaparser.ast.stmt.BlockStmt;
import com.github.javaparser.ast.stmt.Statement;
import com.github.javaparser.ast.type.ClassOrInterfaceType;
import com.github.javaparser.printer.YamlPrinter;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.Dictionary;
import java.util.HashSet;
import java.util.Hashtable;
import java.util.List;
import java.util.Set;

public class TestClassUpdator {
    JavaParser parser;
    boolean force_update = false;
    String extra_params = "";

    public static String main(String[] args) {
        if (args.length < 2) {
            throw new IllegalArgumentException("usage: TestClassEditor <existing_class> <add_class>");
        }
        String existingClass = args[0];
        String addClass = args[1];

        TestClassUpdator editor = new TestClassUpdator();
        if (args.length >= 3) {
            String force = args[2];
            if (force.equals("true"))
                editor.force_update = true;
            for (int i = 2; i < args.length; i++) {
                editor.extra_params += args[i] + " ";
            }
        }
        String result = editor.mergeTestClasses(existingClass, addClass);
        return result;
    }

    public TestClassUpdator() {
        parser = new JavaParser();
    }

    /**
     * merge test methods from add_class to exist_class
     */
    public String mergeTestClasses(String exist_class, String add_class) {
        try {
            CompilationUnit existCU = parser.parse(exist_class).getResult().orElse(null);
            CompilationUnit addCU = parser.parse(add_class).getResult().orElse(null);
            // get class declaration of exist_class
            ClassOrInterfaceDeclaration existClassDecl = getClassDeclaration(existCU)[0];
            if (existClassDecl == null) {
                System.err.println("can't find class declaration in existing class");
                System.err.println(extra_params);
                return add_class;
            }
            // get class declaration of add_class
            if (addCU == null || addCU.getTypes().isEmpty()) { // try to parse incomplete code
                System.err.println("can't parse add code as class");
                System.err.println(extra_params);
                return exist_class;
                // addCU = dealInCompeleteCode(add_class);
                // addClassDecl = getClassDeclaration(addCU);
                // if(addClassDecl==null || addClassDecl.getChildNodes().isEmpty()) {
                // System.err.println("can't find method in add class");
                // return exist_class;
                // }
            }
            ClassOrInterfaceDeclaration[] addClassDeclList = getClassDeclaration(addCU);
            ClassOrInterfaceDeclaration addClassDecl = addClassDeclList[0];
            if (addClassDecl == null) {
                System.err.println("can't find class declaration in add class");
                return exist_class;
            }
            // merge imports
            updateImports(existCU, addCU);
            // merge extends and implements
            mergeExtendsAndImplements(existClassDecl, addClassDecl);
            // add fields
            addFields(existClassDecl, addClassDecl);
            // add annotations
            addAnnotations(existClassDecl, addClassDecl);
            // add inner classes
            if (addClassDeclList.length > 1) {
                ClassOrInterfaceDeclaration[] innerClasses = new ClassOrInterfaceDeclaration[addClassDeclList.length - 1];
                System.arraycopy(addClassDeclList, 1, innerClasses, 0, addClassDeclList.length - 1);
                addInnerClasses(existClassDecl, innerClasses);
            }
            // add test methods
            updateTestMethods(existClassDecl, addClassDecl);
            // sort members
            ClassOrInterfaceDeclaration sorted_decl = sortClassMembers(existClassDecl);
            existCU.remove(existClassDecl);
            existCU.addType(sorted_decl);

            return existCU.toString();
        } catch (Exception e) {
            e.printStackTrace();
            return exist_class;
        }
    }

    /**
     * get class declarations from CompilationUnit
     */
    protected ClassOrInterfaceDeclaration[] getClassDeclaration(CompilationUnit cu) {
        if (cu == null || cu.getTypes().isEmpty()) {
            return new ClassOrInterfaceDeclaration[] {null};
        }
        List<ClassOrInterfaceDeclaration> classes = cu.findAll(ClassOrInterfaceDeclaration.class);
        if (classes.isEmpty()) {
            return new ClassOrInterfaceDeclaration[] {null};
        }
        // sort classes by line number
        classes.sort(Comparator.comparingInt(a -> a.getBegin().map(pos->pos.line).orElse(-1)));
        return classes.toArray(new ClassOrInterfaceDeclaration[0]);
    }

    private CompilationUnit dealInCompeleteCode(String add_code) {
        CompilationUnit addCU = new CompilationUnit();
        ClassOrInterfaceDeclaration addClassDecl = new ClassOrInterfaceDeclaration();
        // get all imports and methods from add_code
        Provider provider = Providers.provider(add_code);

        boolean flag = false;
        do {
            flag = false;
            ImportDeclaration importDecl = parser.parse(ParseStart.IMPORT_DECLARATION, provider).getResult()
                    .orElse(null);
            if (importDecl != null) {
                addCU.addImport(importDecl);
                flag = true;
                String stmt = importDecl.toString();
                add_code = add_code.substring(add_code.indexOf(stmt) + stmt.length());
                provider = Providers.provider(add_code);
            }

            MethodDeclaration methodDecl = parser.parse(ParseStart.METHOD_DECLARATION, provider).getResult()
                    .orElse(null);
            if (methodDecl != null) {
                addClassDecl.addMember(methodDecl.clone());
                flag = true;
                String body = methodDecl.getBody().get().toString();
                add_code = add_code.substring(add_code.indexOf(body) + body.length());
                provider = Providers.provider(add_code);
            }

        } while (flag);
        addClassDecl.setName("TempTestClass");
        addCU.addType(addClassDecl);
        return addCU;
    }

    /**
     * add new imports from new class
     * if force update, remove unused imports
     */
    private void updateImports(CompilationUnit existCU, CompilationUnit addCU) {
        // get all imports from existCU
        Dictionary<String,Boolean> existingImports = new Hashtable<String, Boolean>();
        for (ImportDeclaration importDecl : existCU.getImports()) {
            existingImports.put(importDecl.getNameAsString(), false);
        }
        // add new imports from addCU
        for (ImportDeclaration importDecl : addCU.getImports()) {
            String importName = importDecl.getNameAsString();
            if (existingImports.get(importName) == null) {
                existCU.addImport(importDecl.clone());
            }
            existingImports.put(importName, true);
        }
        if (force_update) {
            // remove unused imports
            List<ImportDeclaration> del_imports = new ArrayList<ImportDeclaration>();
            for (ImportDeclaration importDecl : existCU.getImports()) {
                String importName = importDecl.getNameAsString();
                if (existingImports.get(importName) == false) {
                    del_imports.add(importDecl);
                }
            }
            for (ImportDeclaration importDecl : del_imports) {
                existCU.remove(importDecl);
            }
        }
    }

    private void addAnnotations(ClassOrInterfaceDeclaration existClassDecl, ClassOrInterfaceDeclaration addClassDecl){
        // get all exist Annotations
        Set<String> exist_annotations = new HashSet<String>();
        for (AnnotationExpr exist_anntation: existClassDecl.getAnnotations()){
            exist_annotations.add(exist_anntation.getNameAsString());
        }
        for (AnnotationExpr annotation: addClassDecl.getAnnotations()){
            String anno_name = annotation.getNameAsString();
            if(!exist_annotations.contains(anno_name)){
                existClassDecl.addAnnotation(annotation);
            }
        }
    }

    private void mergeExtendsAndImplements(ClassOrInterfaceDeclaration existClassDecl, ClassOrInterfaceDeclaration addClassDecl) {
        if (force_update){
            // remove extends and implements
            existClassDecl.getExtendedTypes().clear();
            existClassDecl.getImplementedTypes().clear();
        }
        Set<String> exist_implements = new HashSet<>();
        for (ClassOrInterfaceType exist_implement: existClassDecl.getImplementedTypes()){
                exist_implements.add(exist_implement.getNameAsString());
        }
        existClassDecl.setExtendedTypes(new NodeList<>(addClassDecl.getExtendedTypes()));
        for (ClassOrInterfaceType add_implement: addClassDecl.getImplementedTypes()){
            if (!exist_implements.contains(add_implement.getNameAsString())){
                existClassDecl.addImplementedType(add_implement.clone());
            }
        }
    }

    private void addFields(ClassOrInterfaceDeclaration existClassDecl, ClassOrInterfaceDeclaration addClassDecl) {
        // get all fields from addClassDecl
        Set<String> existingFields = new HashSet<>();
        for (FieldDeclaration field : existClassDecl.getFields()) {
            existingFields.add(field.getVariable(0).getNameAsString());
        }
        // add new fields from addClassDecl to existClassDecl
        for (FieldDeclaration field : addClassDecl.getFields()) {
            String fieldName = field.getVariable(0).getNameAsString();
            if (!existingFields.contains(fieldName)) {
                existClassDecl.addMember(field.clone());
            }
        }
    }

    private void addInnerClasses(ClassOrInterfaceDeclaration existClassDecl, 
        ClassOrInterfaceDeclaration[] addClassDeclList) {
        // find exist inner classes
        List<ClassOrInterfaceDeclaration> existingInnerClasses = existClassDecl.findAll(ClassOrInterfaceDeclaration.class);
        Set<String> innerClassesNames = new HashSet<>();
        for (ClassOrInterfaceDeclaration decl: existingInnerClasses){
            innerClassesNames.add(decl.getNameAsString());
        }
        for (ClassOrInterfaceDeclaration addClassDecl : addClassDeclList) {
            String className = addClassDecl.getNameAsString();
            // If the class does not exist in the existing class, add it
            if (!innerClassesNames.contains(className)) {
                // Clone the method to avoid modifying the original AST
                ClassOrInterfaceDeclaration cloneclass = addClassDecl.clone();
                existClassDecl.addMember(cloneclass);
            } else {
                // update inner classes
                ClassOrInterfaceDeclaration existingInnerClass = existingInnerClasses.stream()
                        .filter(decl -> decl.getNameAsString().equals(className))
                        .findFirst()
                        .orElse(null);
                if (existingInnerClass != null) {
                    if (force_update || existingInnerClass.getChildNodes().isEmpty()) {
                        existClassDecl.remove(existingInnerClass);
                        existClassDecl.addMember(addClassDecl.clone());
                    } else { // Compare the length of the method body, and replace if the method body to be
                             // added is longer
                        int exist_length = existingInnerClass.toString().length();
                        int add_length = addClassDecl.toString().length();
                        if (add_length > exist_length) {
                            existClassDecl.remove(existingInnerClass);
                            existClassDecl.addMember(addClassDecl.clone());
                        }
                    }
                }
            }
        }
    }

    private MethodDeclaration getMethodByName(ClassOrInterfaceDeclaration classDecl, String methodName) {
        for (MethodDeclaration method : classDecl.getMethods()) {
            if (method.getNameAsString().equals(methodName)) {
                return method;
            }
        }
        return null;
    }

    /**
     * add new test methods to exist class
     */
    private void updateTestMethods(ClassOrInterfaceDeclaration existClassDecl,
            ClassOrInterfaceDeclaration addClassDecl) {
        // Get the method names in the existing class for checking duplicates
        // Set<String> existingMethodNames = new HashSet<>();
        Dictionary<String, Boolean> existingMethodNames = new Hashtable<String, Boolean>();
        for (MethodDeclaration method : existClassDecl.getMethods()) {
            existingMethodNames.put(method.getNameAsString(), false);
        }
        // Iterate over all methods in the class to be added
        for (MethodDeclaration method : addClassDecl.getMethods()) {
            String methodName = method.getNameAsString();
            // If the method does not exist in the existing class, add it
            if (existingMethodNames.get(methodName)==null) {
                existClassDecl.addMember(method.clone());
            } else {
                // update method body
                MethodDeclaration existingMethod = getMethodByName(existClassDecl, methodName);
                if (existingMethod!= null) {
                    if (force_update || !existingMethod.getBody().isPresent()) {
                        existingMethod.setBody(method.getBody().get().clone());
                    } else { // Compare the length of the method body, and replace if the method body to be
                             // added is longer
                        int exist_length = existingMethod.getBody().get().toString().length();
                        int add_length = method.getBody().get().toString().length();
                        // System.out.println("exist_length: " + exist_length);
                        // System.out.println("add_length: " + add_length);
                        if (add_length > exist_length) {
                            existingMethod.setBody(method.getBody().get().clone());
                        }
                    }
                }
            }
        }
        // Enumeration<String> keys = existingMethodNames.keys();
        // while (keys.hasMoreElements()) {
        //     String methodName = keys.nextElement();
        //     if (existingMethodNames.get(methodName) == false){
        //         MethodDeclaration existingMethod = getMethodByName(existClassDecl, methodName);
        //         existClassDecl.remove(existingMethod);
        //     }
        // }
    }
    
    public void printAST(CompilationUnit cu) {
        if (cu == null) {
            System.out.println("CompilationUnit is null");
            return;
        }
        String yaml = new YamlPrinter(true).output(cu);
        System.out.println(yaml);
    }

    /**
     * add statements in source to the end of target method
     */
    protected MethodDeclaration addStateMent2Method(MethodDeclaration target, MethodDeclaration source){
        if (target.getBody().get().getStatements().size() == 0){
            target = source.clone();
            return target;
        }
        BlockStmt target_body = target.getBody().get();
        if (source.getBody().isPresent()) {
            BlockStmt block = source.getBody().get();
            for (Statement stmt : block.getStatements()) {
                target_body.addStatement(stmt.clone());
            }
        }
        return target;
    }

    /**
     * Sort members of a class in the order: fields, setup/teardown functions, methods, test functions
     */
    public ClassOrInterfaceDeclaration sortClassMembers(ClassOrInterfaceDeclaration classDecl) {
        ClassOrInterfaceDeclaration sorted = new ClassOrInterfaceDeclaration();
        String class_name = classDecl.getNameAsString();
        sorted.setName(class_name);
        sorted.setExtendedTypes(new NodeList<>(classDecl.getExtendedTypes()));
        sorted.setImplementedTypes(new NodeList<>(classDecl.getImplementedTypes()));
        // Get all fields, inner class, and annotatins
        List<FieldDeclaration> fields = new ArrayList<>(classDecl.getFields());
        List<ClassOrInterfaceDeclaration> inner_classes = classDecl.findAll(ClassOrInterfaceDeclaration.class);
        List<AnnotationExpr> annotations =  classDecl.getAnnotations();
        // Get all methods and separate them by annotation
        MethodDeclaration before_each = new MethodDeclaration();
        MethodDeclaration before_all = new MethodDeclaration();
        MethodDeclaration after_each = new MethodDeclaration();
        MethodDeclaration after_all = new MethodDeclaration();
        List<MethodDeclaration> no_anntations = new ArrayList<>();
        List<MethodDeclaration> test_methods = new ArrayList<>();
        for (MethodDeclaration method : classDecl.getMethods()) {
            if (method.getAnnotations().isEmpty()) {
                no_anntations.add(method.clone());
            } else {
                if (method.getAnnotationByName("BeforeEach").isPresent()) {
                    before_each = addStateMent2Method(before_each, method);
                } else if (method.getAnnotationByName("BeforeAll").isPresent()) {
                    before_all = addStateMent2Method(before_all, method);
                } else if (method.getAnnotationByName("AfterEach").isPresent()) {
                    after_each = addStateMent2Method(after_each, method);
                } else if (method.getAnnotationByName("AfterAll").isPresent()) {
                    after_all = addStateMent2Method(after_all, method);
                } else {
                    test_methods.add(method.clone());
                }
            }
        }
        // Add members back in the desired order
        for (AnnotationExpr anntation: annotations){
            sorted.addAnnotation(anntation);
        }
        for (FieldDeclaration field : fields) {
            sorted.addMember(field.clone());
        }
        for (ClassOrInterfaceDeclaration innerClass : inner_classes) {
            if (innerClass.getNameAsString().equals(class_name)) continue;
            sorted.addMember(innerClass.clone());
        }
        if (before_all.getBody().isPresent() && before_all.getBody().get().getStatements().size() > 0) {
            sorted.addMember(before_all);
        }
        if (before_each.getBody().isPresent() && before_each.getBody().get().getStatements().size() > 0) {
            sorted.addMember(before_each);
        }
        if (after_each.getBody().isPresent() && after_each.getBody().get().getStatements().size() > 0) {
            sorted.addMember(after_each);
        }
        if (after_all.getBody().isPresent() && after_all.getBody().get().getStatements().size() > 0) {
            sorted.addMember(after_all);
        }
        for (MethodDeclaration method : no_anntations) {
            sorted.addMember(method.clone());
        }
        for (MethodDeclaration method : test_methods) {
            sorted.addMember(method.clone());
        }
        return sorted;
    }
}
