package temp;

import spoon.Launcher;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.CtModel;
import spoon.reflect.visitor.Filter;
import spoon.reflect.declaration.CtMethod;

import java.util.Set;

import fr.inria.controlflow.ControlFlowBuilder;
import fr.inria.controlflow.ControlFlowEdge;
import fr.inria.controlflow.ControlFlowGraph;

public class CFGBuilder {
    public void buildCFG() {
        Launcher launcher = new Launcher();
        launcher.addInputResource("src");
        CtModel model = launcher.buildModel();
        CtClass<?> ctClass = model.getElements((Filter<CtClass<?>>) element -> true)
                .stream()
                .filter(c -> c.getQualifiedName().equals("extractor.JavaParserExtractor"))
                .findFirst()
                .orElseThrow(() -> new RuntimeException("Class CodeInfoExtractor not found"));
        CtClass<?> ctClass2 = model.getElements((Filter<CtClass<?>>) element -> true)
                .stream()
                .filter(c -> c.getQualifiedName().equals("extractor.JavaParserExtractor"))
                .findFirst()
                .orElseThrow(() -> new RuntimeException("Class CodeInfoExtractor not found"));
        CtMethod<?> method = ctClass.getMethodsByName("extractJavadoc").get(0); // Changed to getMethodsByName
        // CtMethod<?> method2 = ctClass.getMethodsByName("extractClassInfo").get(0); //
        // Changed to getMethodsByName
        ControlFlowBuilder builder = new ControlFlowBuilder();
        // builder.visitCtClass(ctClass);
        // builder.visitCtClass(ctClass2);
        builder.visitCtMethod(method);
        // ControlFlowGraph cfg = builder.build(ctClass2);
        // ControlFlowGraph cfg = builder.build(method);
        // builder.build(method2);
        ControlFlowGraph cfg = builder.getResult();
        cfg.simplify(); // Merge/remove invalid nodes
        String dot = cfg.toGraphVisText(); // Generate GraphViz DOT text
        // String dot = cfg.toString();
        System.out.println(dot);
        Set<ControlFlowEdge> edges = cfg.edgeSet();
        // for (ControlFlowEdge e : edges) {
        //     int source = e.getSourceNode().getId();
        //     int target = e.getTargetNode().getId();
        //     // String pos = e.getTargetNode().getStatement().getPosition().toString();
        //     Boolean kind = e.isBackEdge();
        //     // System.err.println(e.toString());
        //     System.out.println("source: " + source + ", target: " + target);
        //     // System.out.println("pos: " + pos);
        //     System.out.println("kind: " + kind);
        // }
    }
}
