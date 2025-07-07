package codegraph;

import java.util.Set;

import com.google.gson.JsonObject;

import spoon.Launcher;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.declaration.CtType;

public class ControlFlowGraphBuilder {
    CtModel model;
    public ControlFlowGraphBuilder(String source_path){
        Launcher launcher = new Launcher();
        launcher.addInputResource(source_path);
        model = launcher.buildModel();
    }

    protected JsonObject buildGraph4Class(CtClass<?> ctClass){
        JsonObject classGraph = new JsonObject();
        Set<CtMethod<?>> methods = ctClass.getMethods();
        for (CtMethod<?> ctMethod : methods) {
            // String signature 
        }
        return classGraph;
    }

    public JsonObject buildGraph4Project(){
        JsonObject graph = new JsonObject();
        model.getAllPackages().forEach(ctPackage -> {
            Set<CtType<?>> types = ctPackage.getTypes();
            for (CtType<?> ctType : types) {
                if (ctType.isClass()) {
                    CtClass<?> ctClass = (CtClass<?>) ctType;
                    String class_fqn = ctClass.getQualifiedName();
                    JsonObject classGraph = buildGraph4Class(ctClass);
                    graph.add(class_fqn, classGraph);
                }
            }
        });
        return graph;
    }
}
