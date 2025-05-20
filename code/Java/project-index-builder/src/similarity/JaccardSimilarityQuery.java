package similarity;

import org.apache.lucene.index.*;
import org.apache.lucene.search.*;

import java.io.IOException;
import java.util.Arrays;

public class JaccardSimilarityQuery extends Query {
    private final String dvField; // "cfunc_dv" or "cfield_dv"
    private final long[] queryOrds; // Ordinals of terms in C(q) from the dictionary (must be sorted)
    private final int querySize; // C(q).size()
    private final float boostWeight; // w_c or w_f

    public JaccardSimilarityQuery(String dvField, long[] queryOrds, int querySize, float boostWeight) {
        this.dvField = dvField;
        this.queryOrds = queryOrds.clone();
        this.querySize = querySize;
        this.boostWeight = boostWeight;
        Arrays.sort(this.queryOrds);
    }

    @Override
    public Weight createWeight(IndexSearcher searcher, ScoreMode scoreMode, float boost) throws IOException {
        return new JaccardWeight(this, boost * boostWeight);
    }

    private class JaccardWeight extends Weight {
        private final float weight;

        protected JaccardWeight(Query parent, float weight) {
            super(parent);
            this.weight = weight;
        }

        // public void extractTerms(java.util.Set<Term> terms) {
        // }

        @Override
        public boolean isCacheable(LeafReaderContext ctx) {
            return true;
        }

        @Override
        public Explanation explain(LeafReaderContext context, int doc) throws IOException {
            ScorerSupplier scorerSupplier = scorerSupplier(context);
            if (scorerSupplier == null) {
                return Explanation.noMatch("No document values for field " + dvField);
            }
            Scorer scorer = scorerSupplier.get(1);
            if (scorer == null) {
                return Explanation.noMatch("No scorer available for document " + doc);
            }
            int newDoc = scorer.iterator().advance(doc);
            if (newDoc != doc) {
                return Explanation.noMatch("Document " + doc + " does not match");
            }
            float score = scorer.score();
            return Explanation.match(score, "Jaccard similarity score for field " + dvField);
        }

        /**
         * for a newer version of Lucene, we can use ScorerSupplier instead of Scorer
         */
        @Override
        public ScorerSupplier scorerSupplier(LeafReaderContext context) throws IOException {
            SortedSetDocValues dv = context.reader().getSortedSetDocValues(dvField);
            if (dv == null)
                return null; // Skip if a segment does not have this field
            return new JaccardScorerSupplier(this, dv, queryOrds, querySize, weight);
        }

        @Override
        public Scorer scorer(LeafReaderContext ctx) throws IOException {
            SortedSetDocValues dv = ctx.reader().getSortedSetDocValues(dvField);
            if (dv == null) return null; // Skip if a segment does not have this field
            return new JaccardScorer(this, dv, queryOrds, querySize, weight);
        }

    }

    @Override
    public String toString(String field) {
        return "JaccardSim(field=" + dvField + ", ords=" +
                queryOrds.length + ", boost=" + boostWeight + ")";
    }

    @Override
    public boolean equals(Object o) {
        if (this == o) return true;
        if (o == null || getClass() != o.getClass()) return false;

        JaccardSimilarityQuery that = (JaccardSimilarityQuery) o;

        if (querySize != that.querySize) return false;
        if (Float.compare(that.boostWeight, boostWeight) != 0) return false;
        if (!dvField.equals(that.dvField)) return false;
        return Arrays.equals(queryOrds, that.queryOrds);
    }

    @Override
    public int hashCode() {
        int result = 1;
        result = 31 * result + dvField.hashCode();
        result = 31 * result + Arrays.hashCode(queryOrds);
        result = 31 * result + querySize;
        result = 31 * result + Float.floatToIntBits(boostWeight);
        return result;
    }

    @Override
    public void visit(QueryVisitor visitor) {
        if (visitor.acceptField(dvField)) {
            visitor.visitLeaf(this);
        }
    }
}
