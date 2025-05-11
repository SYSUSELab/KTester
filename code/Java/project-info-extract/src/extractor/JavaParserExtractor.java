package extractor;
import com.github.javaparser.JavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.type.Type;
import com.github.javaparser.ast.ImportDeclaration;
import com.github.javaparser.ast.Node;
import com.github.javaparser.ast.NodeList;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.ConstructorDeclaration;
import com.github.javaparser.ast.body.EnumDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.github.javaparser.ast.expr.Expression;
import com.github.javaparser.ast.expr.FieldAccessExpr;
import com.github.javaparser.ast.expr.MethodCallExpr;
import com.github.javaparser.ast.expr.NameExpr;
import com.github.javaparser.ast.expr.ObjectCreationExpr;
import com.github.javaparser.resolution.TypeSolver;
import com.github.javaparser.resolution.declarations.ResolvedConstructorDeclaration;
import com.github.javaparser.resolution.declarations.ResolvedMethodDeclaration;
import com.github.javaparser.resolution.declarations.ResolvedValueDeclaration;
import com.github.javaparser.resolution.types.ResolvedType;
import com.github.javaparser.symbolsolver.JavaSymbolSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.CombinedTypeSolver;
import com.github.javaparser.symbolsolver.resolution.typesolvers.ReflectionTypeSolver;

import infostructure.CallMethodInfo;
import infostructure.VariableInfo;

import java.io.IOException;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

public class JavaParserExtractor {
    Path datasetRoot;
    Path outputPath;
    CombinedTypeSolver typeSolver;
    JavaParser parser;

    public JavaParserExtractor() {
        this.setParser();
    }

    private void setParser() {
        typeSolver = new CombinedTypeSolver(new ReflectionTypeSolver());
        JavaSymbolSolver symbolSolver = new JavaSymbolSolver(typeSolver);
        parser = new JavaParser();
        parser.getParserConfiguration().setSymbolResolver(symbolSolver);
        return;
    }

    protected void addTypeSolver(TypeSolver solver) {
        this.typeSolver.add(solver);
        JavaSymbolSolver symbolSolver = new JavaSymbolSolver(typeSolver);
        parser.getParserConfiguration().setSymbolResolver(symbolSolver);
        return;
    }

    protected static boolean isJavaFile(Path file) {
        String fileName = file.getFileName().toString();
        if (fileName.endsWith(".java")) {
            return true;
        }
        // try {
        // String content = Files.readString(file);
        // return content.contains("class ") || content.contains("interface ") ||
        // content.contains("public static void main");
        // } catch (IOException e) {
        // return false;
        // }
        return false;
    }

    protected static boolean isJarFile(Path file) {
        String fileName = file.getFileName().toString();
        if (fileName.endsWith(".jar")) {
            return true;
        }
        return false;
    }

    public CompilationUnit parseJavaFile(Path javaFile) throws IOException {
        CompilationUnit cu = parser.parse(javaFile).getResult().orElse(null);
        return cu;
    }

    public List<String> getImports(CompilationUnit cu) {
        // get imports
        List<String> imports = new ArrayList<>();
        for (ImportDeclaration imp_node : cu.getImports()) {
            imports.add(imp_node.toString().trim());
        }
        return imports;
    }

    protected String extractJavadoc(Node node) {
        final String javadoc;
        if (node instanceof ClassOrInterfaceDeclaration) {
            ClassOrInterfaceDeclaration classDecl = (ClassOrInterfaceDeclaration) node;
            javadoc = classDecl.getJavadocComment().map(text -> text.getContent()).orElse(null);
            return javadoc;
        } else if (node instanceof MethodDeclaration) {
            MethodDeclaration methodDecl = (MethodDeclaration) node;
            javadoc = methodDecl.getJavadocComment().map(text -> text.getContent()).orElse(null);
            return javadoc;
        } else if (node instanceof ConstructorDeclaration) {
            ConstructorDeclaration consDecl = (ConstructorDeclaration) node;
            javadoc = consDecl.getJavadocComment().map(text -> text.getContent()).orElse(null);
            return javadoc;
        } else if (node instanceof EnumDeclaration) {
            EnumDeclaration enumDecl = (EnumDeclaration) node;
            javadoc = enumDecl.getJavadocComment().map(text -> text.getContent()).orElse(null);
            return javadoc;
        }
        return null;
    }

    protected CallMethodInfo resolveQualifiedName(ObjectCreationExpr object_crt) {
        String qualified_sig = object_crt.getTypeAsString();
        List <VariableInfo> args = new ArrayList<VariableInfo>();
        String return_type = qualified_sig;
        ResolvedConstructorDeclaration rsv_const = null;
        NodeList<Expression> arguments = object_crt.getArguments();
        int arg_count = arguments.size();
        try {
            rsv_const = object_crt.resolve();
            String qualified_name = rsv_const.declaringType().getQualifiedName();
            String method_sig = rsv_const.getSignature();
            return_type = rsv_const.declaringType().getQualifiedName();
            int rsv_arg_count = rsv_const.getNumberOfParams();
            for (int i = 0; i < arg_count; i++) {
                String arg_type;
                if (i >= rsv_arg_count) {
                    arg_type = rsv_const.getParam(rsv_arg_count-1).describeType().replace("...", "");
                }
                else{
                    arg_type = rsv_const.getParam(i).describeType();
                }
                method_sig = method_sig.replaceAll("([0-9a-zA-Z]+\\.)+", "");
                String arg_name = arguments.get(i).toString();
                VariableInfo arg_info = new VariableInfo(arg_name, arg_type);
                args.add(arg_info);
            }
            qualified_sig = qualified_name + "." + method_sig;
        } catch (Exception e) {
            for (int i = 0; i < arg_count; i++) {
                String arg_type = "unresolved";
                String arg_name = arguments.get(i).toString();
                VariableInfo arg_info = new VariableInfo(arg_name, arg_type); 
                args.add(arg_info);
            }
            System.out.println("Error: " + e.getMessage());
        }
        CallMethodInfo method_call_info = new CallMethodInfo(qualified_sig, args, return_type);
        return method_call_info;
    }

    protected CallMethodInfo resolveQualifiedName(MethodCallExpr method_call) {
        String qualified_sig = method_call.getNameAsString();
        List <VariableInfo> args = new ArrayList<VariableInfo>();
        String return_type = "unresolved";
        ResolvedMethodDeclaration rsv_method = null;
        NodeList<Expression> arguments = method_call.getArguments();
        int arg_count = arguments.size();
        try {
            rsv_method = method_call.resolve();
            String qualified_name = rsv_method.declaringType().getQualifiedName();
            String method_sig = rsv_method.getSignature();
            return_type = rsv_method.getReturnType().describe();
            int rsv_arg_count = rsv_method.getNumberOfParams();
            for (int i = 0; i < arg_count; i++) {
                String arg_type;
                if (i >= rsv_arg_count) {
                    arg_type = rsv_method.getParam(rsv_arg_count-1).describeType().replace("...", "");
                }
                else{
                    arg_type = rsv_method.getParam(i).describeType();
                }
                method_sig = method_sig.replaceAll("([0-9a-zA-Z]+\\.)+", "");
                String arg_name = arguments.get(i).toString();
                VariableInfo arg_info = new VariableInfo(arg_name, arg_type);
                args.add(arg_info);
            }
            qualified_sig = qualified_name + "." + method_sig;
        } catch (Exception e) {
            for (int i = 0; i < arg_count; i++) {
                String arg_type = "unresolved";
                String arg_name = arguments.get(i).toString();
                VariableInfo arg_info = new VariableInfo(arg_name, arg_type); 
                args.add(arg_info);
            }
            System.out.println("Error: " + e.getMessage());
        }
        CallMethodInfo method_call_info = new CallMethodInfo(qualified_sig, args, return_type);
        return method_call_info;
    }

    protected VariableInfo resolveQualifiedName(FieldAccessExpr field_access) {
        String field_name = field_access.getNameAsString();
        String field_type = "unresolved";
        String declaring_class = "";
        try {
            ResolvedValueDeclaration rsv_field = field_access.resolve();
            field_type = rsv_field.getType().describe();
            // get full name of the field, including package name
            if (rsv_field.isField()) {
                declaring_class = rsv_field.asField().declaringType().getQualifiedName();
                field_name = declaring_class + "." + field_name;
            } else if (rsv_field.isEnumConstant()) {
                field_name = field_type + "." + field_name;
            }
        } catch (Exception e) {
            System.out.println("Error: " + e.getMessage());
        }
        VariableInfo field_info = new VariableInfo(field_name, field_type);
        return field_info;
    }

    protected VariableInfo resolveQualifiedName(NameExpr name_expr) {
        VariableInfo var_info = null;
        try {
            ResolvedValueDeclaration rsv_name = name_expr.resolve();
            if (rsv_name.isField()) {
                String field_type = rsv_name.getType().describe();
                String declaring_class = rsv_name.asField().declaringType().getQualifiedName();
                String field_name = declaring_class + "." + name_expr.getNameAsString();
                VariableInfo field_info = new VariableInfo(field_name, field_type);
                return field_info;
            } else if (rsv_name.isEnumConstant()) {
                String field_type = rsv_name.getType().describe();
                String field_name = field_type + "." + name_expr.getNameAsString();
                VariableInfo field_info = new VariableInfo(field_name, field_type);
                return field_info;
            }
        } catch (Exception e) {
            return null;
        }
        return var_info;
    }

    protected String resolveType(Expression expr, String simple) {
        String fqn = "";
        try {
            ResolvedType resolvedType = expr.calculateResolvedType();
            fqn = resolvedType.describe();
        } catch (Exception e) {
            fqn = simple;
            System.out.println("Error: " + e.getMessage());
        }
        return fqn;
    }

    protected String resolveType(Type type) {
        String fqn = "";
        try {
            ResolvedType resolvedType = type.resolve();
            fqn = resolvedType.describe();
        } catch (Exception e) {
            System.out.println("Error: " + e.getMessage());
            fqn = type.toString();
        }
        return fqn;
    }

    protected int[] getPosition(Node node) {
        int start_line = node.getBegin().map(pos->pos.line-1).orElse(-1);
        int end_line = node.getEnd().map(pos->pos.line).orElse(-1);
        if (start_line >= 0 && end_line == -1) {
            end_line = start_line + 1;
        }
        return new int[]{start_line, end_line};
    }
}
