import com.github.javaparser.JavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.ImportDeclaration;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.FieldDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;

import java.util.HashSet;
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
            // 解析两个测试类
            CompilationUnit existCU = parser.parse(exist_class).getResult().orElse(null);
            CompilationUnit addCU = parser.parse(add_class).getResult().orElse(null);
            if (existCU == null ) {
                System.err.println("can't parse existing class or add class");
                return "";
            }
            if (addCU == null) {
                System.err.println("can't parse add class");
                return exist_class;
            }
            
            // 获取两个类的声明
            ClassOrInterfaceDeclaration existClassDecl = getClassDeclaration(existCU);
            if (existClassDecl == null) {
                System.err.println("can't find class declaration in existing class");
                return add_class;
            }
            ClassOrInterfaceDeclaration addClassDecl = getClassDeclaration(addCU);
            if (addClassDecl == null) {
                System.err.println("can't find class declaration in add class");
                return exist_class;
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
        // 获取现有类中的方法名称集合，用于检查重复
        Set<String> existingMethodNames = getMethodNames(existClassDecl);
        // 遍历需要添加的类中的所有方法
        for (MethodDeclaration method : addClassDecl.getMethods()) {
            String methodName = method.getNameAsString();
            // // 判断方法是不是测试方法
            // if (method.getAnnotationByName("Test").isEmpty()) {
            //     continue;
            // }
            // 如果方法不存在于现有类中，则添加
            if (!existingMethodNames.contains(methodName)) {
                // 克隆方法以避免修改原始AST
                MethodDeclaration clonedMethod = method.clone();
                existClassDecl.addMember(clonedMethod);
            } else {
                // 比较方法体的长度，如果需要添加的方法体更长，则替换
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
