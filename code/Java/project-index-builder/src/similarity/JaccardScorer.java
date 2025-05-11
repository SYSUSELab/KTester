package similarity;

import java.io.IOException;
import java.util.Arrays;

import org.apache.lucene.index.SortedSetDocValues;
import org.apache.lucene.search.DocIdSetIterator;
import org.apache.lucene.search.ScoreMode;
import org.apache.lucene.search.Scorer;
import org.apache.lucene.search.Weight;

public class JaccardScorer extends Scorer {
    private final SortedSetDocValues dv;
    private final long[] queryOrds;
    private final int querySize;
    private final float boostweight;
    private int doc = -1;

    protected JaccardScorer(Weight weight, SortedSetDocValues dv,long[] queryOrds, int querySize, float boostWeight) {
        super(weight);
        this.dv = dv;
        this.queryOrds = queryOrds;
        this.querySize = querySize;
        this.boostweight = boostWeight;
    }

    @Override
    public int docID() {
        return doc;
    }

    @Override
    public float score() throws IOException {
        if (!dv.advanceExact(doc))
            return 0f;

        // 优化：如果queryOrds为空，直接返回0分
        if (queryOrds.length == 0) 
            return 0f;
        
        // 优化：使用更高效的方式计算交集
        int docCount = 0, intersection = 0;
        
        
        // 预先分配足够大小的数组，避免动态扩容
        // 使用docValueCount() 获取当前文档的doc values数量
        int valueCount = dv.docValueCount();
        long[] docOrds = new long[valueCount]; // 初始容量，如果不够会自动扩容
        int docOrdsSize = 0;
        long ord;
        // 第一次遍历：收集文档的所有ordinals
        for(int i = 0; i < valueCount; i++) {
            ord = dv.nextOrd();
            docCount++;
            docOrds[docOrdsSize++] = ord;
        }
        
        // 如果文档没有任何term，直接返回0分
        if (docCount == 0)
            return 0f;
        
        // 优化：如果文档的term数量远大于查询的term数量，使用查询的term去查找
        if (queryOrds.length < docCount / 10) { // 阈值可以根据实际情况调整
            for (long queryOrd : queryOrds) {
                // 使用二分查找在文档ordinals中查找查询ordinal
                int pos = Arrays.binarySearch(docOrds, 0, docOrdsSize, queryOrd);
                if (pos >= 0) {
                    intersection++;
                }
            }
        } else {
            // 否则，使用文档的term去查找
            for (long docOrd : docOrds) {
                if (Arrays.binarySearch(queryOrds, docOrd) >= 0) {
                    intersection++;
                }
            }
        }

        // J = |I| / (|Q| + |D| - |I|)
        int union = querySize + docCount - intersection;
        double jaccard = (union == 0 ? 0.0 : (double) intersection / union);
        return (float) (jaccard * boostweight);
    }

    @Override
    public DocIdSetIterator iterator() {
        //  use the docID iterator of dv directly, only the doc with dv is scored
        return new DocIdSetIterator() {
            @Override
            public int docID() {
                return doc;
            }

            @Override
            public int nextDoc() throws IOException {
                return (doc = dv.nextDoc());
            }

            @Override
            public int advance(int target) throws IOException {
                return (doc = dv.advance(target));
            }

            @Override
            public long cost() {
                return dv.cost();
            }
        };
    }

    public ScoreMode scoreMode() {
        // 我们不依赖其他 score，只输出自定义分值
        return ScoreMode.COMPLETE;
    }

    @Override
    public float getMaxScore(int upTo) throws IOException {
        return boostweight;
    }
}