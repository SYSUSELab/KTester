package infostructure;

import java.util.List;
import com.github.javaparser.ast.AccessSpecifier;

public class MethodInfo extends FunctionInfo {
    int start_line;
    int end_line;
    CallMethodInfo[] call_methods;
    VariableInfo[] external_fields;
    String return_type;
    AccessSpecifier access_type;

    public MethodInfo( String sig, 
            List<VariableInfo> param, 
            int[] position,
            CallMethodInfo[] cmethods,
            VariableInfo[] fields,
            String rtn_type,
            AccessSpecifier access_type) {
        super(sig, param);
        this.start_line = position[0];
        this.end_line = position[1];
        this.call_methods = cmethods;
        this.external_fields = fields;
        this.return_type = rtn_type;
        this.access_type = access_type;
    }
}
