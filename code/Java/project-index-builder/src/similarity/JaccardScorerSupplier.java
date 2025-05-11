package similarity;

import java.io.IOException;

import org.apache.lucene.index.SortedSetDocValues;
import org.apache.lucene.search.Scorer;
import org.apache.lucene.search.ScorerSupplier;
import org.apache.lucene.search.Weight;

/**
 * JaccardScorerSupplier - 优化版本
 * 1. 添加缓存机制，避免重复创建Scorer对象
 * 2. 提前检查查询条件是否有效
 */
public class JaccardScorerSupplier extends ScorerSupplier {
    private final SortedSetDocValues dv;
    private final long[] queryOrds;
    private final int querySize;
    private final float weight;
    private final Weight parentWeight;
    
    // 缓存创建的Scorer对象
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
        // // 如果查询条件无效，直接返回null
        // if (queryOrds.length == 0 && querySize > 0) {
        //     return null;
        // }
        
        // 使用缓存的Scorer对象，如果已经创建过
        if (cachedScorer == null) {
            cachedScorer = new JaccardScorer(parentWeight, dv, queryOrds, querySize, weight);
        }
        return cachedScorer;
    }

    @Override
    public long cost() {
        // 如果查询条件无效，返回最小成本
        if (queryOrds.length == 0 && querySize > 0) {
            return 0;
        }
        return dv.cost();
    }
}