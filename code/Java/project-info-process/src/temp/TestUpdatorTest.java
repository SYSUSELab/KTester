package temp;

import editcode.TestClassUpdator;

public class TestUpdatorTest {
    public static void main(String[] args) {
        // test1();
        test2();
        // testMemberOrder();
    }
    static void test1() {
        String existingClass = "import org.junit.Test;\n" +
        "import static org.junit.Assert.*;\n\n" +
        "@ExtendWith(MockitoExtension.class)\n" +
        "public class CalculatorTest {\n" +
        " @Mock\n" +
        " private int lance;\n" +
        " @Test\n" +
        " public void testAdd() {\n" +
        " assertEquals(4, 2 + 2);\n" +
        " }\n" +
        "}\n";

        String classToAdd = "import org.junit.Test;\n" +
        "import static org.junit.Assert.*;\n\n" +
        "public class CalculatorTest {\n" +
        " @Test\n" +
        " public void testSubtract() {\n" +
        " assertEquals(0, 2 - 2);\n" +
        " }\n\n" +
        " @Test\n" +
        " public void testMultiply() {\n" +
        " assertEquals(4, 2 * 2);\n" +
        " }\n" +
        "}\n";

        String result = TestClassUpdator.main(new String[] { existingClass, classToAdd
        });
        System.out.println("===== 合并后的测试类 =====");
        System.out.println(result);
    }
    static void test2() {
        String existingClass2 = "import org.junit.Test;\n" +
        "import static org.junit.Assert.*;\n" +
        "import static org.test.Assert.*;\n" +
        "public class StringUtilTest {\n" +
        " @Test\n" +
        " public void testConcat() {\n" +
        " assertEquals(\"HelloWorld\", \"Hello\" + \"World\");\n" +
        " }\n" +
        " class Myclass { " +
        "     void test() {}" +
        "     public float b; " +
        " }" +
        "}\n";

        String classToAdd2 = "import org.junit.Test;\n" +
        "import static org.junit.Assert.*;\n" +
        "import java.util.Arrays;\n" +
        "import java.util.List;\n\n" +
        "public class StringUtilTest {\n" +
        " @Test\n" +
        " public void testConcat() {\n" +
        " List<String> parts = Arrays.asList(\"Hello,World\".split(\",\"));\n" +
        " assertEquals(\"HelloWorld\", \"Hello\" + \"World\");\n" +
        " }\n" +
        " @Test\n" +
        " public void testSplit() {\n" +
        " List<String> parts = Arrays.asList(\"Hello,World\".split(\",\"));\n" +
        " assertEquals(2, parts.size());\n" +
        " assertEquals(\"Hello\", parts.get(0));\n" +
        " assertEquals(\"World\", parts.get(1));\n" +
        " }\n" +
        " class Myclass { " +
        "     void test() {}" +
        "     public int a; " +
        " }" +
        "}\n";

        String result2 = TestClassUpdator.main(new String[] { existingClass2,
        classToAdd2});
        System.out.println("\n\n===== 带有新导入的合并测试类 =====");
        System.out.println(result2);
    }
    static void testMemberOrder(){
        String existingClass3 = "package org.apache.commons.collections4.map;\n" +
        "import org.junit.jupiter.api.*;\n" +
        "import org.junit.jupiter.api.extension.ExtendWith;\n" +
        "import org.mockito.*;\n" +
        "import static org.mockito.Mockito.*;\n" +
        "import org.mockito.junit.jupiter.MockitoExtension;\n" +
        "@ExtendWith(MockitoExtension.class)\n" +
        "class Flat3Map_equals_Test implements BaseDict {\n" +
            "private Flat3Map<Integer, String> flat3Map;\n" +
            "@BeforeAll\n" +
            "static void setupBeforeAll() {\n" +
            "// Any resource allocation that needs to happen once for all tests can be added here\n"+
            "}\n" +
            "@BeforeEach\n" +
            "void setupBeforeEach() {\n" +
                "flat3Map = new Flat3Map<>();\n" +
            "}\n" +
            "@AfterEach\n" +
            "void teardownAfterEach() {\n" +
            "   // Cleanup individual test resources (if any)\n" +
            "}\n" +
            "@AfterAll\n" +
            "static void teardownAfterAll() {\n" +
            "   // Cleanup resources that were allocated in setupBeforeAll (if any)\n" +
            "}\n" +
            "@Test\n" +
            "void testEquals_SameObject() {\n" +
            "    assertTrue(flat3Map.equals(flat3Map));\n" +
            "}\n" +
            "@Test\n" +
            "void testEquals_Null() {\n" +
            "    assertFalse(flat3Map.equals(null));\n" +
            "}\n" +
        "}";
        String classToAdd3 = "package org.apache.commons.collections4.map;\n" +
        "import org.junit.jupiter.api.*;\n" +
        "import org.junit.jupiter.api.extension.ExtendWith;\n" +
        "import static org.junit.jupiter.api.Assertions.*;\n" +
        "import org.mockito.*;\n" +
        "import static org.mockito.Mockito.*;\n" +
        "import org.mockito.junit.jupiter.MockitoExtension;\n" +
        "@Timeout(100)\n" +
        "class Flat3Map_equals_Test extends JavaParserExtractor implements BaseImportDict {\n" +
            "@BeforeEach\n" +
            "void setup() {\n" +
            "    String s = \"abc\";\n" +
            "}\n" +
            "private Flat3Map<String, String> createTestMap(int size, Object... keyValuePairs) {\n" +
                "Flat3Map<Integer, String> map = new Flat3Map<>();\n" +
                "for (int i = 0; i < size; i++) {\n" +
                    "Integer key = (Integer) keyValuePairs[2 * i];\n" +
                    "String value = (String) keyValuePairs[2 * i + 1];\n" +
                    "map.put(key, value);\n" +
                "}\n" +
                "return map;\n" +
            "}\n" +
        "}\n";
        String result3 = TestClassUpdator.main(new String[] { existingClass3, classToAdd3});
        System.out.println("\n\n===== 测试成员顺序 =====");
        System.out.println(result3);
    }
}