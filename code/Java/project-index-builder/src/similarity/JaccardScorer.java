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

        // if queryOrds is empty, return 0
        if (queryOrds.length == 0) 
            return 0f;
        
        int docCount = 0, intersection = 0;
        // allocate arrays with initial capacity
        int valueCount = dv.docValueCount();
        long[] docOrds = new long[valueCount];
        int docOrdsSize = 0;
        long ord;
        // collect all ordinals of the document
        for(int i = 0; i < valueCount; i++) {
            ord = dv.nextOrd();
            docCount++;
            docOrds[docOrdsSize++] = ord;
        }
        // if the document has no term, return 0
        if (docCount == 0)
            return 0f;
        // if the document has more than 10 times of query terms, use query terms to find
        if (queryOrds.length < docCount / 10) {
            for (long queryOrd : queryOrds) {
                // search for queryOrd in docOrds by binary search
                int pos = Arrays.binarySearch(docOrds, 0, docOrdsSize, queryOrd);
                if (pos >= 0) {
                    intersection++;
                }
            }
        } else {
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
        // just output our custom score
        return ScoreMode.COMPLETE;
    }

    @Override
    public float getMaxScore(int upTo) throws IOException {
        return boostweight;
    }
}