public class TestClassEditorTest {
    public static void main(String[] args) {
        String existingClass = 
            "import org.junit.Test;\n" +
            "import static org.junit.Assert.*;\n\n" +
            "@ExtendWith(MockitoExtension.class)\n" +
            "public class CalculatorTest {\n" +
            "    @Mock\n" +
            "    private int lance;\n" +
            "    @Test\n" +
            "    public void testAdd() {\n" +
            "        assertEquals(4, 2 + 2);\n" +
            "    }\n" +
            "}\n";
        
        String classToAdd = 
            "import org.junit.Test;\n" +
            "import static org.junit.Assert.*;\n\n" +
            "public class CalculatorTest {\n" +
            "    @Test\n" +
            "    public void testSubtract() {\n" +
            "        assertEquals(0, 2 - 2);\n" +
            "    }\n\n" +
            "    @Test\n" +
            "    public void testMultiply() {\n" +
            "        assertEquals(4, 2 * 2);\n" +
            "    }\n" +
            "}\n";
        
        String result = TestClassEditor.main(new String[]{existingClass, classToAdd});
        System.out.println("===== 合并后的测试类 =====");
        System.out.println(result);
        
        String existingClass2 = 
            "import org.junit.Test;\n" +
            "import static org.junit.Assert.*;\n\n" +
            "public class StringUtilTest {\n" +
            "    @Test\n" +
            "    public void testConcat() {\n" +
            "        assertEquals(\"HelloWorld\", \"Hello\" + \"World\");\n" +
            "    }\n" +
            "}\n";
        
        String classToAdd2 = 
            "import org.junit.Test;\n" +
            "import static org.junit.Assert.*;\n" +
            "import java.util.Arrays;\n" +
            "import java.util.List;\n\n" +
            "public class StringUtilTest {\n" +
            "    @Test\n" +
            "    public void testConcat() {\n" +
            "        List<String> parts = Arrays.asList(\"Hello,World\".split(\",\"));\n" +
            "        assertEquals(\"HelloWorld\", \"Hello\" + \"World\");\n" +
            "    }\n" +
            "    @Test\n" +
            "    public void testSplit() {\n" +
            "        List<String> parts = Arrays.asList(\"Hello,World\".split(\",\"));\n" +
            "        assertEquals(2, parts.size());\n" +
            "        assertEquals(\"Hello\", parts.get(0));\n" +
            "        assertEquals(\"World\", parts.get(1));\n" +
            "    }\n" +
            "}\n";
        
        String result2  = TestClassEditor.main(new String[]{existingClass2, classToAdd2});
        System.out.println("\n\n===== 带有新导入的合并测试类 =====");
        System.out.println(result2);
    }
}