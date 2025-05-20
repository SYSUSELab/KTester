import com.github.javaparser.JavaParser;
import com.github.javaparser.ParseResult;
import com.github.javaparser.ParseStart;
import com.github.javaparser.Provider;
import com.github.javaparser.Providers;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.ImportDeclaration;
import com.github.javaparser.ast.body.BodyDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.stmt.Statement;
import com.github.javaparser.printer.YamlPrinter;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class TestClassEditor {
    JavaParser parser;

    public static String main(String[] args) {
        if (args.length < 2) {
            throw new IllegalArgumentException("usage: TestClassEditor <existing_class> <add_class>");
        }
        String existingClass = args[0];
        String addClass = args[1];

        TestClassEditor editor = new TestClassEditor();
        String result = editor.mergeTestClasses(existingClass, addClass);
        return result;
    }

    public TestClassEditor() {
        parser = new JavaParser();
    }
    /**
     * merge test methods from add_class to exist_class
     */
    public String mergeTestClasses(String exist_class, String add_class) {
        try {
            CompilationUnit existCU = parser.parse(exist_class).getResult().orElse(null);
            CompilationUnit addCU = parser.parse(add_class).getResult().orElse(null);
            if (existCU == null ) {
                System.err.println("can't parse existing class or add class");
                return "";
            }

            ClassOrInterfaceDeclaration addClassDecl = getClassDeclaration(addCU);
            if(addCU.getTypes().isEmpty()){ // try to parse incomplete code 
                System.err.println("can't parse add code as class");
                return exist_class;
                // addCU = dealInCompeleteCode(add_class);
                // addClassDecl = getClassDeclaration(addCU);
                // if(addClassDecl==null || addClassDecl.getChildNodes().isEmpty()) {
                //     System.err.println("can't find method in add class");
                //     return exist_class;
                // }
            }
            // YamlPrinter printer = new YamlPrinter(true);
            // System.err.println(printer.output(addCU));
            // get class declaration
            ClassOrInterfaceDeclaration existClassDecl = getClassDeclaration(existCU);
            if (existClassDecl == null) {
                System.err.println("can't find class declaration in existing class");
                return add_class;
            }
            // merge imports
            mergeImports(existCU, addCU);
            // add fields
            addFields(existClassDecl, addClassDecl);
            // add test methods
            addNewTestMethods(existClassDecl, addClassDecl);
            return existCU.toString();
        } catch (Exception e) {
            e.printStackTrace();
            return exist_class;
        }
    }

    private CompilationUnit dealInCompeleteCode (String add_code){
        CompilationUnit addCU = new CompilationUnit();
        ClassOrInterfaceDeclaration addClassDecl = new ClassOrInterfaceDeclaration();
        // get all imports and methods from add_code
        Provider provider = Providers.provider(add_code);

        boolean flag = false;
        do {
            flag = false;
            ImportDeclaration importDecl = parser.parse(ParseStart.IMPORT_DECLARATION, provider).getResult().orElse(null);
            if (importDecl != null) {
                addCU.addImport(importDecl);
                flag = true;
                String stmt = importDecl.toString();
                add_code = add_code.substring(add_code.indexOf(stmt)+stmt.length());
                provider = Providers.provider(add_code);
            }
                
            MethodDeclaration methodDecl = parser.parse(ParseStart.METHOD_DECLARATION, provider).getResult().orElse(null);
            if (methodDecl != null) {
                addClassDecl.addMember(methodDecl.clone());
                flag = true;
                String body = methodDecl.getBody().get().toString();
                add_code = add_code.substring(add_code.indexOf(body)+body.length());
                provider = Providers.provider(add_code);
            }
            
        } while(flag);
        addClassDecl.setName("TempTestClass");
        addCU.addType(addClassDecl);
        return addCU;
    }
    
    /**
     * get class declaration
     */
    private ClassOrInterfaceDeclaration getClassDeclaration(CompilationUnit cu) {
        if (cu.getTypes().isEmpty()) {
            return null;
        }
        return cu.getTypes().stream()
                .filter(type -> type instanceof ClassOrInterfaceDeclaration)
                .map(type -> (ClassOrInterfaceDeclaration) type)
                .findFirst()
                .orElse(null);
    }
    
    /**
     * merge imports from two CompilationUnit
     */
    private void mergeImports(CompilationUnit existCU, CompilationUnit addCU) {
        // get all imports from existCU
        Set<String> existingImports = new HashSet<>();
        for (ImportDeclaration importDecl : existCU.getImports()) {
            existingImports.add(importDecl.getNameAsString());
        }
        // add new imports from addCU
        for (ImportDeclaration importDecl : addCU.getImports()) {
            String importName = importDecl.getNameAsString();
            if (!existingImports.contains(importName)) {
                existCU.addImport(importDecl.clone());
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
    
    /**
     * get all method names in class
     */
    private Set<String> getMethodNames(ClassOrInterfaceDeclaration classDecl) {
        Set<String> methodNames = new HashSet<>();
        for (MethodDeclaration method : classDecl.getMethods()) {
            methodNames.add(method.getNameAsString());
        }
        return methodNames;
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
    private void addNewTestMethods(ClassOrInterfaceDeclaration existClassDecl,                             ClassOrInterfaceDeclaration addClassDecl) {
        // Get the method names in the existing class for checking duplicates
        Set<String> existingMethodNames = getMethodNames(existClassDecl);
        // Iterate over all methods in the class to be added
        for (MethodDeclaration method : addClassDecl.getMethods()) {
            String methodName = method.getNameAsString();
            // // Check if the method is a test method
            // if (method.getAnnotationByName("Test").isEmpty()) {
            //     continue;
            // }
            // If the method does not exist in the existing class, add it
            if (!existingMethodNames.contains(methodName)) {
                // Clone the method to avoid modifying the original AST
                MethodDeclaration clonedMethod = method.clone();
                existClassDecl.addMember(clonedMethod);
            } else {
                // Compare the length of the method body, and replace if the method body to be added is longer
                MethodDeclaration existingMethod = getMethodByName(existClassDecl, methodName);
                if (existingMethod != null && method.getBody().isPresent()){
                    int exist_length = existingMethod.getBody().isPresent() ? existingMethod.getBody().get().toString().length() : 0;
                    int add_length = method.getBody().get().toString().length();
                    if (add_length > exist_length) {
                        existingMethod.setBody(method.getBody().get().clone());
                    }
                }
            }
        }
    }
}
