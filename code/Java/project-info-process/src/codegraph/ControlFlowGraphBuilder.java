package codegraph;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import com.google.gson.Gson;
import com.google.gson.JsonObject;

import fr.inria.controlflow.ControlFlowBuilder;
import fr.inria.controlflow.ControlFlowEdge;
import fr.inria.controlflow.ControlFlowGraph;
import fr.inria.controlflow.ControlFlowNode;
import spoon.Launcher;
import spoon.reflect.CtModel;
import spoon.reflect.cu.SourcePosition;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtExecutable;
import spoon.reflect.declaration.CtInterface;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.declaration.CtType;

public class ControlFlowGraphBuilder {
    CtModel model;
    Gson gson;

    public ControlFlowGraphBuilder(String source_path) {
        Launcher launcher = new Launcher();
        launcher.addInputResource(source_path);
        model = launcher.buildModel();
        this.gson = new Gson();
    }

    class Edge {
        int source;
        int target;
        Boolean is_back;
        Edge(int source, int target, Boolean is_back){
            this.source = source;
            this.target = target;
            this.is_back = is_back;
        }
    }

    class Graph {
        CfgNode[] nodes;
        Edge[] edges;
        Graph(CfgNode[] nodes, Edge[] edges) {
            this.nodes = nodes;
            this.edges = edges;
        }
    }

    private void addNodeFromControlFlow(ControlFlowNode flow_node, Set<CfgNode> nodes) {
        int id = flow_node.getId();
        try {
            SourcePosition pos = flow_node.getStatement().getPosition();
            nodes.add(new CfgNode(id, flow_node.getKind(), pos.getLine()-1, pos.getEndLine()-1));
        } catch (Exception e) {
            nodes.add(new CfgNode(id, flow_node.getKind()));
        }
    }

    private String transformSignature(CtExecutable<?> method, String class_name) {
        String osig = method.getSignature();
        int l = osig.indexOf('(');
        int r = osig.lastIndexOf(')');
        if (l < 0 || r < 0 || r < l) return osig;

        String methodName = method.getSimpleName().replace("<init>", class_name);
        String params = osig.substring(l + 1, r);
        if (params.trim().isEmpty()) return methodName + "()";

        String[] paramTypes = params.split(",");
        StringBuilder sb = new StringBuilder();
        sb.append(methodName).append("(");
        int plen = paramTypes.length;
        for (int i = 0; i < plen; i++) {
            String type = paramTypes[i].trim();
            type = type.replace("$", ".");
            int lastDot = type.lastIndexOf('.');
            String simpleName = lastDot >= 0 ? type.substring(lastDot + 1) : type;
            sb.append(simpleName);
            if (i != plen - 1) sb.append(", ");
        }
        sb.append(")");
        return sb.toString();
    }

    protected JsonObject buildGraph4Method(CtElement method) {
        ControlFlowBuilder builder = new ControlFlowBuilder();
        ControlFlowGraph cfg = builder.build(method);
        cfg.simplify();
        // get all nodes and edges
        Set<ControlFlowEdge> edges = cfg.edgeSet();
        Set<CfgNode> nodes = new HashSet<CfgNode>();
        List<Edge> edgesList = new ArrayList<Edge>();
        for (ControlFlowEdge edge : edges) {
            // add source node and target node
            ControlFlowNode source_node = edge.getSourceNode();
            ControlFlowNode target_node = edge.getTargetNode();
            addNodeFromControlFlow(source_node, nodes);
            addNodeFromControlFlow(target_node, nodes);
            // add edge
            int source_id = source_node.getId();
            int target_id = target_node.getId();
            edgesList.add(new Edge(target_id, source_id, edge.isBackEdge()));
        }
        // add nodes and edges to graph
        CfgNode[] nodesArray = nodes.toArray(new CfgNode[0]);
        Arrays.sort(nodesArray);
        Graph graph = new Graph(nodesArray, edgesList.toArray(new Edge[0]));
        JsonObject graph_json = this.gson.toJsonTree(graph).getAsJsonObject();
        return graph_json;
    }

    protected JsonObject buildGraph4Class(CtClass<?> ctClass) {
        JsonObject classGraph = new JsonObject();
        Set<CtMethod<?>> methods = ctClass.getMethods();
        String class_name = ctClass.getSimpleName();
        for (CtMethod<?> method : methods) {
            if (method.getBody() == null)  continue;
            String signature = transformSignature(method, class_name);

            JsonObject method_graph = buildGraph4Method(method);
            classGraph.add(signature, method_graph);
        }

        ctClass.getConstructors().stream().forEach(constructor -> {
            if (constructor.getBody() !=null){
                String signature = transformSignature(constructor, class_name);
                JsonObject constructor_graph = buildGraph4Method(constructor);
                classGraph.add(signature, constructor_graph);
            }
        });
        return classGraph;
    }

    protected JsonObject buildGraph4Interface(CtInterface<?> ctInterface) {
        JsonObject interfaceGraph = new JsonObject();
        Set<CtMethod<?>> methods = ctInterface.getMethods();
        String class_name = ctInterface.getSimpleName();
        for (CtMethod<?> method : methods) {
            if (method.getBody() == null)  continue;
            String signature = transformSignature(method, class_name);
            JsonObject method_graph = buildGraph4Method(method);
            interfaceGraph.add(signature, method_graph);
        }
        return interfaceGraph;
    }

    public JsonObject buildGraph4Project() {
        JsonObject graph = new JsonObject();
        model.getAllPackages().forEach(ctPackage -> {
            Set<CtType<?>> types = ctPackage.getTypes();
            for (CtType<?> ctType : types) {
                if (ctType.isClass()) {
                    CtClass<?> ctClass = (CtClass<?>) ctType;
                    String class_fqn = ctClass.getQualifiedName();
                    JsonObject classGraph = buildGraph4Class(ctClass);
                    graph.add(class_fqn, classGraph);
                    ctClass.getNestedTypes().forEach(nestedType -> {
                        if (nestedType.isClass()) {
                            CtClass<?> nestedClass = (CtClass<?>) nestedType;
                            String nestedClass_fqn = nestedClass.getQualifiedName().replace("$", ".");
                            JsonObject nestedClassGraph = buildGraph4Class(nestedClass);
                            graph.add(nestedClass_fqn, nestedClassGraph);
                        } else if (nestedType.isInterface()) {
                            CtInterface<?> nestedInterface = (CtInterface<?>) nestedType;
                            String nestedInterface_fqn = nestedInterface.getQualifiedName().replace("$", ".");
                            JsonObject nestedInterfaceGraph = buildGraph4Interface(nestedInterface);
                            graph.add(nestedInterface_fqn, nestedInterfaceGraph);
                        }
                    });
                } else if (ctType.isInterface()) {
                    CtInterface<?> ctInterface = (CtInterface<?>) ctType;
                    String interface_fqn = ctInterface.getQualifiedName();
                    JsonObject interfaceGraph = buildGraph4Interface(ctInterface);
                    graph.add(interface_fqn, interfaceGraph);
                }
            }
        });
        return graph;
    }
}
