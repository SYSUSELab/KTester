package extractor;

import java.util.Dictionary;
import java.util.Enumeration;
import java.util.HashSet;
import java.util.Hashtable;
import java.util.List;
import java.util.Set;

import com.github.javaparser.ast.CompilationUnit;
import com.github.javaparser.ast.ImportDeclaration;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

public interface BaseImportDict {
    Dictionary<String, Set<String>> import_dict = new Hashtable<String, Set<String>>();

    default void initImportDict(){
        import_dict.put("Test", Set.of("import org.junit.jupiter.api.*;"));
        import_dict.put("assertEquals", Set.of("import static org.junit.jupiter.api.Assertions.*;"));
        import_dict.put("ExtendWith", Set.of("import org.junit.jupiter.api.extension.ExtendWith;"));

        import_dict.put("MockitoExtension", Set.of("import org.mockito.junit.jupiter.MockitoExtension;"));
        import_dict.put("Mock", Set.of("import org.mockito.*;"));


        import_dict.put("ParameterizedTest", Set.of("import org.junit.jupiter.params.ParameterizedTest;"));
        import_dict.put("Arguments", Set.of("import org.junit.jupiter.params.provider.Arguments;"));
        import_dict.put("MethodSource", Set.of("import org.junit.jupiter.params.provider.MethodSource"));
        import_dict.put("CsvSource", Set.of("import org.junit.jupiter.params.provider.CsvSource;"));
        import_dict.put("ValueSource", Set.of("import org.junit.jupiter.params.provider.ValueSource;"));
        import_dict.put("EnumSource", Set.of("import org.junit.jupiter.params.provider.EnumSource;"));

        import_dict.put("Method", Set.of("import java.lang.reflect.Method;"));
        import_dict.put("Field", Set.of("import java.lang.reflect.Field;"));        
    }

    default void addImportDict(CompilationUnit cu){
        List<ImportDeclaration> imports = cu.getImports();
        if (imports == null) 
            return;

        for (ImportDeclaration import_decl : imports) {
            String import_stmt = import_decl.toString().strip();
            String[] split = import_stmt.replace(";", "").replace(".*", "").split("\\.");
            String simple_name = split[split.length - 1];
            if (import_dict.get(simple_name) == null) 
                import_dict.put(simple_name, new HashSet<String>());
            Set<String> dict = new HashSet<>(import_dict.get(simple_name));
            dict.add(import_stmt);
            import_dict.put(simple_name, dict);
        }
    }

    default JsonObject constructImportDict(){
        JsonObject import_dict_json = new JsonObject();
        Enumeration<String> keys = import_dict.keys();
        while (keys.hasMoreElements()) {
            String key = keys.nextElement();
            Set<String> value = import_dict.get(key);
            JsonArray import_list = new JsonArray();
            value.forEach(import_stmt -> {
                import_list.add(import_stmt);
            });
            import_dict_json.add(key, import_list);
        };
        return import_dict_json;
    } 
}
