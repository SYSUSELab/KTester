package editcode;

import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

import spoon.Launcher;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.CtClass;
import spoon.reflect.declaration.CtElement;
import spoon.reflect.declaration.CtField;
import spoon.reflect.declaration.CtMethod;
import spoon.reflect.declaration.CtType;
import spoon.reflect.visitor.Filter;
import spoon.support.compiler.VirtualFile;

public class TestClassSterilizer {
    public static String main(String[] args){
        if (args.length < 2) {
            throw new IllegalArgumentException("Usage: TestClassSterilizer <original code> <operation>");
        }
        String originalCode = args[0];
        String operation = args[1];

        TestClassSterilizer testClassSterilizer = new TestClassSterilizer();
        switch (operation) {
            case "inner_class":
                return testClassSterilizer.removeRedundantInnerClass(originalCode);
            default:
                throw new IllegalArgumentException("Invalid operation: " + operation);
        }
    }

    Launcher launcher;
    CtModel model;
    CtClass<?>[] class_decs;

    public TestClassSterilizer() {
        launcher = new Launcher();
    }

    public String removeRedundantInnerClass(String code) {
        launcher.addInputResource(new VirtualFile(code));
        launcher.buildModel();
        model = launcher.getModel();

        getClassDeclaration();
        CtClass<?> root_class = class_decs[0];
        String root_class_name = root_class.getSimpleName();
        HashMap<String, CtClass<?>> merged_classes = new HashMap<>();
        merged_classes.put(root_class_name, root_class);
        for (CtClass<?> inner: getChildClass(root_class)) {
            String class_name = inner.getSimpleName();
            if (!merged_classes.containsKey(class_name)) {
                merged_classes.put(class_name, inner);
            } else {
                mergeInnerClass(merged_classes.get(class_name), inner);
                root_class.removeNestedType(inner);
            }
        }
        return root_class.prettyprint();
    }

    protected void getClassDeclaration() {
        List<CtClass<?>> class_nodes =  model.getElements((Filter<CtClass<?>>) element -> true);
        if (class_nodes.isEmpty()) class_decs = new CtClass<?>[] {null};
        class_nodes.sort(Comparator.comparingInt(a -> a.getPosition().getLine()));
        class_decs = class_nodes.toArray(new CtClass<?>[0]);
    }

    protected CtClass<?>[] getChildClass(CtClass<?> root_class) {
        List<CtClass<?>> child_classes = new ArrayList<CtClass<?>>();
        for (CtElement nested: root_class.getDirectChildren()) {
            if (nested instanceof CtClass) {
                for (CtClass<?> cdec : class_decs)
                    if (cdec.equals(nested)) child_classes.add(cdec);
            }
        }
        return child_classes.toArray(new CtClass<?>[0]);
    }

    protected void mergeInnerClass(CtClass<?> target, CtClass<?> source) {
        mergeFields(target, source);
        mergeMethods(target, source);
        // merge extends and implements
        MergeExtendandImplements(target, source);
        MergeModifiers(target, source);

        Set<CtType<?>> source_nested = source.getNestedTypes();
        if (source_nested.size() > 0) {
            HashMap<String, CtType<?>> nested_map = new HashMap<String, CtType<?>>();
            for (CtType<?> inner: target.getNestedTypes()) {
                nested_map.put(inner.getSimpleName(), inner);
            }
            for (CtType<?> inner: source_nested) {
                if (nested_map.containsKey(inner.getSimpleName())) {
                    CtType<?> itype = nested_map.get(inner.getSimpleName());
                    if (itype instanceof CtClass && inner instanceof CtClass){
                        mergeInnerClass((CtClass<?>) itype, (CtClass<?>) inner);
                    }
                } else {
                    target.addNestedType(inner.clone());
                }
            }
        }
    }

    protected void MergeModifiers(CtClass<?> target, CtClass<?> source) {
        Set<String> modifiers = new HashSet<>();
        target.getFormalCtTypeParameters().forEach(m -> modifiers.add(m.getSimpleName()));
        source.getFormalCtTypeParameters().forEach(m -> {
            if (!modifiers.contains(m.toString())) target.addFormalCtTypeParameter(m.clone());
        });
    }

    protected void MergeExtendandImplements(CtClass<?> target, CtClass<?> source) {
        if (source.getSuperclass() != null && target.getSuperclass() == null)
            target.setSuperclass(source.getSuperclass().clone());
        Set<String> interfaces = new HashSet<>();
        target.getSuperInterfaces().forEach(i -> interfaces.add(i.getSimpleName()));
        source.getSuperInterfaces().forEach(i -> {
            if (!interfaces.contains(i.getSimpleName())) target.addSuperInterface(i.clone());
        });
    }

    protected void mergeFields(CtClass<?> target, CtClass<?> source) {
        HashSet<String> fieldNames = new HashSet<String>();
        for (CtField<?> field : target.getFields()) {
            fieldNames.add(field.getSimpleName());
        }
        for (CtField<?> field : source.getFields()) {
            if (!fieldNames.contains(field.getSimpleName())) {
                fieldNames.add(field.getSimpleName());
                target.addField(field.clone());
            }
        }
    }

    protected void mergeMethods(CtClass<?> target, CtClass<?> source) {
        HashSet<String> methodNames = new HashSet<String>();
        for (CtMethod<?> method : target.getMethods()) {
            methodNames.add(method.getSimpleName());
        }
        for (CtMethod<?> method : source.getMethods()) {
            if (!methodNames.contains(method.getSimpleName())) {
                methodNames.add(method.getSimpleName());
                target.addMethod(method.clone());
            } else {
                CtMethod<?> targetMethod = target.getMethod(method.getSimpleName());
                CtMethod<?> sourceMethod = source.getMethod(method.getSimpleName());
                if (sourceMethod.prettyprint().length() > targetMethod.prettyprint().length()) {
                    target.removeMethod(targetMethod);
                    target.addMethod(method.clone());
                }
            }
        }
    }
}
