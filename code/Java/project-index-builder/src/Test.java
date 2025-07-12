import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

public class Test{
    public static void main(String[] args) throws Exception {
        System.out.println("Hello, World!");
        for (int i = 0; i < args.length; i++) {
            System.out.println(args[i]);
        }

        // test IndexBuilder
        String mode = "group";
        String code_path = "../../../dataset/project_index/json";
        String index_path = "../../../dataset/project_index/lucene";
        String[] arguments = new String[] {mode, code_path, index_path};
        IndexBuilder.main(arguments);

        // // test CodeSearcher
        // String project = "../../../dataset/projects/batch-processing-gateway";
        // String index_path = "../../../dataset/project_index/lucene/batch-processing-gateway";
        // JsonArray query_list = new JsonArray();
        // JsonObject singal_query = new JsonObject();
        // singal_query.addProperty("sig", "test1");
        // JsonArray function_list = new JsonArray();
        // function_list.add("com.apple.spark.core.ApplicationSubmissionHelper.looksLikeFilePath(String)");
        // function_list.add("com.apple.spark.util.ExceptionUtils.getExceptionNameAndMessage(Throwable)");
        // singal_query.add("function", function_list);
        // JsonArray field_list = new JsonArray();
        // field_list.add("com.fasterxml.jackson.dataformat.yaml.YAMLGenerator.Feature.WRITE_DOC_START_MARKER");
        // field_list.add("javax.ws.rs.core.Response.Status.BAD_REQUEST");
        // singal_query.add("field", field_list);
        // query_list.add(singal_query);
        // JsonObject singal2 = singal_query.deepCopy();
        // field_list.add("com.fasterxml.jackson.dataformat.yaml.YAMLGenerator.Feature.MINIMIZE_QUOTES");
        // singal_query.add("field", field_list);
        // singal_query.addProperty("sig", "test2");
        // query_list.add(singal2);

        // String query = query_list.toString();
        // String[] arguments = new String[] {project, index_path, query};
        // String result = CodeSearcher.main(arguments);
        // System.out.println(result);
    }
}
