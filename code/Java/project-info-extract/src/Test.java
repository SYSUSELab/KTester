public class Test {
    public static void main(String[] args) throws Exception {
        System.out.println("Class test, args:");
        for (int i = 0; i < args.length; i++) {
            System.out.println(args[i]);
        }

        // String dataet_dir = "../../../dataset/projects";
        // String[] arg = new String[] {dataet_dir};
        // // DatasetPreparation.main(arg);
        // DatasetPrepare.main(arg);

        // String source_dir = "../../../dataset/projects";
        // String output_dir = "../../../dataset/project_index/json";
        // String[] arg = new String[] { source_dir, output_dir };
        // PreProcessor.main(arg);

        // CFGBuilder cfgBuilder = new CFGBuilder();
        // cfgBuilder.buildCFG();
    }
}
