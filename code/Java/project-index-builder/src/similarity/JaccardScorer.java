package similarity;

import java.io.IOException;
import java.util.Arrays;

import org.apache.lucene.index.SortedSetDocValues;
import org.apache.lucene.search.DocIdSetIterator;
import org.apache.lucene.search.Scorer;
import org.apache.lucene.search.Weight;

public class JaccardScorer extends Scorer {
    private final SortedSetDocValues dv;
    private final long[] queryOrds;
    private final int querySize;
    private final float weight;
    private int doc = -1;

    protected JaccardScorer(Weight weight, SortedSetDocValues dv,
            long[] queryOrds, int querySize, float boostWeight) {
        super();
        this.dv = dv;
        this.queryOrds = queryOrds;
        this.querySize = querySize;
        this.weight = boostWeight;
    }

    @Override
    public int docID() {
        return doc;
    }

    @Override
    public float score() throws IOException {
        if (!dv.advanceExact(doc))
            return 0f;

        // Calculate the term ordinals of doc and the intersection size with queryOrds
        int docCount = 0, intersection = 0;
        long ord;
        while ((ord = dv.nextOrd()) != SortedSetDocValues.NO_MORE_DOCS) {
            docCount++;
            if (Arrays.binarySearch(queryOrds, ord) >= 0) {
                intersection++;
            }
        }

        // J = |I| / (|Q| + |D| - |I|)
        int union = querySize + docCount - intersection;
        double jaccard = (union == 0 ? 0.0 : (double) intersection / union);
        return (float) (jaccard * weight);
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

    // public ScoreMode scoreMode() {
    //     // 我们不依赖其他 score，只输出自定义分值
    //     return ScoreMode.COMPLETE;
    // }

    @Override
    public float getMaxScore(int upTo) throws IOException {
        return weight;
    }
}