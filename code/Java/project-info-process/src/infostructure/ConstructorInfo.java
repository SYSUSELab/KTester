package infostructure;

import java.util.List;

import com.github.javaparser.ast.AccessSpecifier;

public class ConstructorInfo extends FunctionInfo {
    CallMethodInfo[] call_methods;
    VariableInfo[] external_fields;

    public ConstructorInfo(String sig, 
            List<VariableInfo> params, 
            int[] position,
            AccessSpecifier access_type,
            CallMethodInfo[] cmethods,
            VariableInfo[] fields) {
        super(sig, params, position, access_type);
        this.call_methods = cmethods;
        this.external_fields = fields;
    }
}
