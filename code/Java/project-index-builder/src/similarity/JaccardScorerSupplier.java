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
        return new JaccardScorer(parentWeight, dv, queryOrds, querySize, weight);
    }

    @Override
    public long cost() {
        return dv.cost();
    }
}