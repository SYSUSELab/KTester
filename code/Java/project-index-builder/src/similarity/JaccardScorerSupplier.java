package similarity;

import java.io.IOException;

import org.apache.lucene.index.SortedSetDocValues;
import org.apache.lucene.search.Scorer;
import org.apache.lucene.search.ScorerSupplier;
import org.apache.lucene.search.Weight;

public class JaccardScorerSupplier extends ScorerSupplier {
    private final SortedSetDocValues dv;
    private final long[] queryOrds;
    private final int querySize;
    private final float weight;
    private final Weight parentWeight;
    
    // Cache the created Scorer object
    private JaccardScorer cachedScorer;

    protected JaccardScorerSupplier(Weight parentWeight, SortedSetDocValues dv,
            long[] queryOrds, int querySize, float boostWeight) {
        this.parentWeight = parentWeight;
        this.dv = dv;
        this.queryOrds = queryOrds;
        this.querySize = querySize;
        this.weight = boostWeight;
    }

    @Override
    public Scorer get(long leadCost) throws IOException {
        // // if the query is invalid, return null
        // if (queryOrds.length == 0 && querySize > 0) {
        //     return null;
        // }
        
        // use the cached Scorer object if it has been created
        if (cachedScorer == null) {
            cachedScorer = new JaccardScorer(parentWeight, dv, queryOrds, querySize, weight);
        }
        return cachedScorer;
    }

    @Override
    public long cost() {
        if (queryOrds.length == 0 && querySize > 0) {
            return 0;
        }
        return dv.cost();
    }
}