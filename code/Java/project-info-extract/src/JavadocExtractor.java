// package ase2023;

import com.github.javaparser.JavaParser;
import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.body.ClassOrInterfaceDeclaration;
import com.github.javaparser.ast.body.MethodDeclaration;
import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

public class JavadocExtractor {
    public static void main(String[] args) throws IOException {
        // Path datasetRoot = Paths.get(args[0]);
        // Path outputDir = Paths.get(args[1]);
        Path datasetRoot = Paths.get("D:/Study/myevaluation/demo&code/dataset/puts");
        Path outputDir = Paths.get("D:/Study/myevaluation/demo&code/dataset/puts_json_test");

        if (!Files.exists(outputDir)) {
            Files.createDirectories(outputDir);
        }

        Files.list(datasetRoot).filter(Files::isDirectory).forEach(subDataset -> {
            try {
                JsonObject datasetJson = processDataset(subDataset.getFileName().toString(), subDataset);
                Gson gson = new GsonBuilder().setPrettyPrinting().disableHtmlEscaping().create();
                String json = gson.toJson(datasetJson);
                Files.writeString(outputDir.resolve(subDataset.getFileName().toString() + ".json"), json);
                System.out.println("JSON 生成成功: " + subDataset.getFileName().toString() + ".json");
            } catch (IOException e) {
                e.printStackTrace();
            }
        });
    }

    private static JsonObject processDataset(String datasetName, Path sourceDir) throws IOException {
        JsonObject datasetJson = new JsonObject();
        datasetJson.addProperty("dataset", datasetName);

        JsonObject classesJson = new JsonObject();
        Files.walk(sourceDir)
                .filter(Files::isRegularFile)
                .filter(JavadocExtractor::isJavaFile)
                .forEach(javaFile -> {
                    try {
                        JsonObject classInfo = extractJavadoc(javaFile);
                        if (classInfo != null) {
                            classInfo.entrySet().forEach(entry -> classesJson.add(entry.getKey(), entry.getValue()));
                        }
                    } catch (IOException e) {
                        e.printStackTrace();
                    }
                });

        datasetJson.add("classes", classesJson);
        return datasetJson;
    }

    private static boolean isJavaFile(Path file) {
        String fileName = file.getFileName().toString();
        if (fileName.endsWith(".java")) {
            return true;
        }
        try {
            String content = Files.readString(file);
            return content.contains("class ") || content.contains("interface ") || content.contains("public static void main");
        } catch (IOException e) {
            return false;
        }
    }

    private static JsonObject extractJavadoc(Path javaFile) throws IOException {
        CompilationUnit cu = new JavaParser().parse(javaFile).getResult().orElse(null);
        if (cu == null) return null;

        String packageName = cu.getPackageDeclaration().map(pd -> pd.getNameAsString() + ".").orElse("");

        JsonObject classJson = new JsonObject();
        for (ClassOrInterfaceDeclaration classDecl : cu.findAll(ClassOrInterfaceDeclaration.class)) {
            String fullClassName = packageName + classDecl.getNameAsString();
            JsonObject singleClassInfo = new JsonObject();
            singleClassInfo.addProperty("Javadoc", classDecl.getJavadocComment().map(javadoc -> javadoc.getContent()).orElse(""));

            JsonObject methodsObject = new JsonObject();
            for (MethodDeclaration method : classDecl.getMethods()) {
                method.getJavadocComment().ifPresent(javadoc -> {
                    JsonObject methodJson = new JsonObject();
                    methodJson.addProperty("Javadoc", javadoc.getContent().trim());
                    methodsObject.add(method.getNameAsString(), methodJson);
                });
            }

            if (!methodsObject.entrySet().isEmpty()) {
                singleClassInfo.add("methods", methodsObject);
            }

            classJson.add(fullClassName, singleClassInfo);
        }

        return classJson.entrySet().isEmpty() ? null : classJson;
    }
}

