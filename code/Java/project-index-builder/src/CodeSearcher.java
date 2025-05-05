import org.apache.lucene.analysis.standard.StandardAnalyzer;
import org.apache.lucene.document.Document;
import org.apache.lucene.index.DirectoryReader;
import org.apache.lucene.index.IndexReader;
import org.apache.lucene.index.MultiDocValues;
import org.apache.lucene.index.MultiTerms;
import org.apache.lucene.index.SortedSetDocValues;
import org.apache.lucene.queryparser.classic.MultiFieldQueryParser;
import org.apache.lucene.queryparser.classic.QueryParser;
import org.apache.lucene.queryparser.classic.ParseException;
import org.apache.lucene.search.BooleanClause;
import org.apache.lucene.search.BooleanQuery;
import org.apache.lucene.search.IndexSearcher;
import org.apache.lucene.search.Query;
import org.apache.lucene.search.ScoreDoc;
import org.apache.lucene.search.TopDocs;
import org.apache.lucene.store.Directory;
import org.apache.lucene.store.FSDirectory;
import org.apache.lucene.util.BytesRef;


import com.google.gson.Gson;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

import similarity.JaccardSimilarityQuery;

/**
 * Search Engine class - used to retrieve documents from Lucene index
 */
public class CodeSearcher {
    private final Path project_root;
    private final Path index_path;
    private StandardAnalyzer analyzer;
    private Directory directory;
    private IndexReader index_reader;
    private IndexSearcher index_searcher;
    private SortedSetDocValues func_dv;
    private SortedSetDocValues field_dv;
    private Set<ResultFormat> results;
    private int top_k = 10;
    private float w_c = 0.6f;
    private float w_f = 0.4f;

    public static void main(String[] args) {
        if (args.length < 3) {
            throw new IllegalArgumentException("Arguments for Code Searcher: <project_root> <index path> <query string> <top k>");
        }
        
        Path project = Path.of(args[0]);
        Path index = Path.of(args[1]);
        String query_string = args[2];
        

        if (!Files.isDirectory(project)){
            throw new IllegalArgumentException("project root should be a directory!");
        }
        if (!Files.exists(index)) {
            throw new IllegalArgumentException("index_path should be a directory!");
        }
        
        try {
            CodeSearcher searchEngine = new CodeSearcher(project, index);
            if (args.length >= 4) {
                searchEngine.setTopK(Integer.parseInt(args[3]));
            }
            List<QueryFormat> query_list = searchEngine.parseQueryString(query_string);
            for (QueryFormat query : query_list) {
                searchEngine.search(query);
            }
            // // Search in title and content fields
            // String[] fields = {"title", "content"};
            // List<Document> results = searchEngine.searchByMultipleFields(fields, query_string, 10);
            
            // System.out.println("Found " + results.size() + " matching documents:");
            // for (Document doc : results) {
            //     System.out.println("ID: " + doc.get("id"));
            //     System.out.println("Title: " + doc.get("title"));
            //     System.out.println("Filename: " + doc.get("filename"));
            //     System.out.println("Path: " + doc.get("filepath"));
            //     System.out.println("-------------------");
            // }
            
            searchEngine.close();
            
        } catch (Exception e) {
            System.err.println("Error occurred during search: " + e.getMessage());
            e.printStackTrace();
        }
    }
    
    /**
     * Initialize the search engine
     * @param indexPath Index path
     * @throws IOException If an error occurs while opening the index
     */
    public CodeSearcher(Path project, Path index) throws IOException{
        this.project_root = project;
        this.index_path = index;
        this.analyzer = new StandardAnalyzer();
        this.directory = FSDirectory.open(index_path);
        this.index_reader = DirectoryReader.open(directory);
        this.index_searcher = new IndexSearcher(index_reader);
        this.func_dv = MultiDocValues.getSortedSetValues(index_reader, "cfunc_dv");
        this.field_dv = MultiDocValues.getSortedSetValues(index_reader, "cfield_dv");
    }

    public void setTopK(int top_k) {
        this.top_k = top_k;
    }
    
    /**
     * Search in a single field
     * @param field Field name to search
     * @param queryString Query string
     * @param maxResults Maximum number of results
     * @return List of matching documents
     * @throws IOException If an error occurs during search
     * @throws ParseException If an error occurs while parsing the query
     */
    // public List<Document> searchByField(String field, String queryString, int maxResults) 
    //         throws IOException, ParseException {
    //     QueryParser parser = new QueryParser(field, analyzer);
    //     Query query = parser.parse(queryString);
    //     return executeSearch(query, maxResults);
    // }
    
    // /**
    //  * Search in multiple fields
    //  * @param fields Array of field names to search
    //  * @param queryString Query string
    //  * @param maxResults Maximum number of results
    //  * @return List of matching documents
    //  * @throws IOException If an error occurs during search
    //  * @throws ParseException If an error occurs while parsing the query
    //  */
    // public List<Document> searchByMultipleFields(String[] fields, String queryString, int maxResults) 
    //         throws IOException, ParseException {
    //     MultiFieldQueryParser parser = new MultiFieldQueryParser(fields, analyzer);
    //     Query query = parser.parse(queryString);
    //     return executeSearch(query, maxResults);
    // }
    
    // /**
    //  * Search in multiple fields with specified weights for each field
    //  * @param fields Array of field names to search
    //  * @param weights Weights for each field
    //  * @param queryString Query string
    //  * @param maxResults Maximum number of results
    //  * @return List of matching documents
    //  * @throws IOException If an error occurs during search
    //  * @throws ParseException If an error occurs while parsing the query
    //  */
    // public List<Document> searchByMultipleFieldsWithWeights(String[] fields, Map<String, Float> weights, 
    //         String queryString, int maxResults) throws IOException, ParseException {
    //     MultiFieldQueryParser parser = new MultiFieldQueryParser(fields, analyzer, weights);
    //     Query query = parser.parse(queryString);
    //     return executeSearch(query, maxResults);
    // }
    
    // /**
    //  * Execute search and return results
    //  * @param query Query to execute
    //  * @param maxResults Maximum number of results
    //  * @return List of matching documents
    //  * @throws IOException If an error occurs during search
    //  */
    // private List<Document> executeSearch(Query query, int maxResults) throws IOException {
    //     TopDocs results = index_searcher.search(query, maxResults);
    //     ScoreDoc[] hits = results.scoreDocs;
        
    //     List<Document> documents = new ArrayList<>();
    //     for (ScoreDoc hit : hits) {
    //         // Document doc = indexSearcher.doc(hit.doc);
    //         // documents.add(doc);
    //     }
        
    //     return documents;
    // }
    
    // /**
    //  * Get detailed information of search results
    //  * @param query Query to execute
    //  * @param maxResults Maximum number of results
    //  * @return List of results containing documents and scores
    //  * @throws IOException If an error occurs during search
    //  */
    // public List<SearchResult> getDetailedResults(Query query, int maxResults) throws IOException {
    //     TopDocs results = index_searcher.search(query, maxResults);
    //     ScoreDoc[] hits = results.scoreDocs;
        
    //     List<SearchResult> searchResults = new ArrayList<>();
    //     for (ScoreDoc hit : hits) {
    //         // Document doc = indexSearcher.doc(hit.doc);
    //         // searchResults.add(new SearchResult(doc, hit.score));
    //     }
        
    //     return searchResults;
    // }

    /**
     * Search result class, containing document and relevance score
     */
    // public static class SearchResult {
    //     private final Document document;
    //     private final float score;
        
    //     public SearchResult(Document document, float score) {
    //         this.document = document;
    //         this.score = score;
    //     }
        
    //     public Document getDocument() {
    //         return document;
    //     }
        
    //     public float getScore() {
    //         return score;
    //     }
        
    //     /**
    //      * Get all fields in the document
    //      * @return Mapping of field names and values
    //      */
    //     public Map<String, String> getAllFields() {
    //         Map<String, String> fields = new HashMap<>();
    //         for (String fieldName : document.getFields().stream().map(f -> f.name()).distinct().toArray(String[]::new)) {
    //             fields.put(fieldName, document.get(fieldName));
    //         }
    //         return fields;
    //     }
    // }
    
    private class QueryFormat {
        public String[] function;
        public String[] field;
        public QueryFormat(String [] function, String [] field) {
            this.function = function;
            this.field = field;
        }
    }

    private class ResultFormat {
        public String class_fqn;
        public String signature;
        public String file;
        public int start;
        public int end;
        public float score;
        public ResultFormat(String fqn, String sig, String file, int start, int end, float score) {
            this.class_fqn = fqn;
            this.signature = sig;
            this.file = file;
            this.start = start;
            this.end = end;
            this.score = score;
        }
    }
    
    /**
     * format of query string:
     * [
     *   {
     *     "function": ["xxx","xxx"], 
     *     "field": ["xxx","xxx"],
     *   },
     *   ...
     * ]
     */
    public List<QueryFormat> parseQueryString(String query) {
        JsonArray queryArray = new Gson().fromJson(query, JsonArray.class);
        List<QueryFormat> queryList = new ArrayList<>();
        for (int i = 0; i < queryArray.size(); i++) {
            JsonObject queryObject = queryArray.get(i).getAsJsonObject();
            JsonArray functionArray = queryObject.get("function").getAsJsonArray();
            JsonArray fieldArray =  queryObject.get("field").getAsJsonArray();
            String[] function = new String[functionArray.size()];
            String[] field = new String[fieldArray.size()];
            for (int j = 0; j < functionArray.size(); j++) {
                function[j] = functionArray.get(j).getAsString();
            }
            for (int j = 0; j < fieldArray.size(); j++) {
                field[j] = fieldArray.get(j).getAsString();
            }
            queryList.add(new QueryFormat(function, field));
        }
        return queryList;    
    }

    /**
     * 将一组 term（String）映射到全局 DocValues ordinals。
     *
     * @param reader  已打开的 IndexReader
     * @param dvField DocValues 字段名（如 "calls_dv"）
     * @param terms   查询 term 集合
     * @return 升序排列的 ordinals 数组
     */
    public long[] getOrds(IndexReader reader, String dv_field, String[] terms) {
        // 1) 获取合并后全局的 SortedSetDocValues
        SortedSetDocValues dv = null;
        if (dv_field.equals("cfunc_dv")) {
            dv = this.func_dv;
        } else if (dv_field.equals("cfield_dv")) {
            dv = this.field_dv;
        } else {
            return new long[0];
        }
        // 2) 遍历每个 term，lookupTerm 若 ≥0 则加入列表
        List<Long> ordList = new ArrayList<Long>();
        for (String term : terms) {
            try {
                long ord = dv.lookupTerm(new BytesRef(term));
                if (ord >= 0) {
                    ordList.add(ord);
                }
            } catch (IOException e) {
                continue;
            }
        }
        // 3) 排序，确保后续评分逻辑里可按升序合并
        // Collections.sort(ordList); 
        // 4) 转成 primitive long[]
        long[] ords = ordList.stream().mapToLong(Long::longValue).toArray();
        return ords;
    }

    public void search(QueryFormat query) throws IOException {
        // 拿到 q 的 calls/fields 在各自 dv field 里的 ordinals
        String[] qfunc = query.function;
        String[] qfield = query.field;
        long[] qcOrds = getOrds(index_searcher.getIndexReader(), "cfunc_dv", qfunc);
        long[] qfOrds = getOrds(index_searcher.getIndexReader(), "cfield_dv", qfield);

        // 构造两个 JaccardSimilarityQuery
        Query simCalls  = new JaccardSimilarityQuery("calls_dv",  qcOrds, qfunc.length, w_c);
        Query simFields = new JaccardSimilarityQuery("fields_dv", qfOrds, qfield.length, w_f);
        // 合并成一个 BooleanQuery，让 Lucene 一次倒排遍历就把两者分值累加
        BooleanQuery combined = new BooleanQuery.Builder()
            .add(simCalls, BooleanClause.Occur.SHOULD)
            .add(simFields, BooleanClause.Occur.SHOULD)
            .build();

        TopDocs results = index_searcher.search(combined, top_k);
        for (ScoreDoc sd : results.scoreDocs) {
            Document doc = index_searcher.storedFields().document(sd.doc);
            ResultFormat result = new ResultFormat(doc.get("class_fqn"), 
                        doc.get("signature"),
                        doc.get("file"), 
                        Integer.parseInt(doc.get("start")), 
                        Integer.parseInt(doc.get("end")), 
                        sd.score);
            
        // System.out.printf("doc=%3d  score=%.4f%n", sd.doc, sd.score);
        }

    }
    
    /**
     * Close the index reader and directory
     * @throws IOException If an error occurs during closing
     */
    public void close() throws IOException {
        if (index_reader != null) {
            index_reader.close();
        }
        if (directory != null) {
            directory.close();
        }
    }
    
    /**
     * Get the number of documents in the index
     * @return Number of documents in the index
     */
    public int getDocumentCount() {
        return index_reader.numDocs();
    }
}