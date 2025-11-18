package temp;

import editcode.TestClassSterilizer;

public class TestClassSterilizerTest {
    public static void main(String[] args) {
        test1();
        // test2();
    }
    public static void test1() {
        String class1 = "class $Gson$Types_resolve_Test {\n" + //
                        "    class TestClass<T> {\n" + //
                        "        List<String>[] arrayField;\n" + //
                        "        List<String> listField;\n" + //
                        "        List<? extends String> wildcardField;\n" + //
                        "        List<? extends Number> numbers;\n" + //
                        "        List<? super String> strings;\n" + //
                        "        T field;\n" + //
                        "        Container<T> container;\n" + //
                        "    }\n" + //
                        "    class TestClass<T> extends Container<T> {\n" + //
                        "        T field;\n" + //
                        "    }\n" + //
                        "    class TestClass<T> implements JClass {\n" + //
                        "        T field;\n" + //
                        "        class InnerClass1 {\n" + //
                        "            int field;\n" +
                        "        };\n" + //
                        "    }\n" + //
                        "    class TestClass<T> {\n" + //
                        "        class InnerClass1 extends Jclass{\n" + //
                        "            int field2;\n" +
                        "        };\n" + //
                        "    }\n" + //
                        "    class Container<U> {\n" + 
                        "        List<U> items;\n" + //
                        "    }\n" + 
                        "    class Container<T> {\n" + 
                        "        List<? extends T> items;\n" + //
                        "    }\n" + 
                        "    class Middle<U> {\n" + //
                        "        List<Map<T, U>> complexField;\n" + //
                        "    }\n" + //
                        "    class Middle<T> {\n" + 
                        "        List<Map<T, U>> complexField;\n" + //
                        "    }\n" + 
                        "}";
        TestClassSterilizer sterilizer = new TestClassSterilizer();
        String result = sterilizer.removeRedundantInnerClass(class1);
        System.out.println("++++++++++ result +++++++++++");
        System.out.println(result);
    }
}
