package infostructure;

import java.util.List;
import com.github.javaparser.ast.AccessSpecifier;

public class MethodInfo extends FunctionInfo {
    
    CallMethodInfo[] call_methods;
    VariableInfo[] external_fields;
    String return_type;
    

    public MethodInfo( String sig, 
            List<VariableInfo> param, 
            int[] position,
            AccessSpecifier access_type,
            CallMethodInfo[] cmethods,
            VariableInfo[] fields,
            String rtn_type) {
        super(sig, param, position, access_type);
        this.call_methods = cmethods;
        this.external_fields = fields;
        this.return_type = rtn_type;
    }
}
