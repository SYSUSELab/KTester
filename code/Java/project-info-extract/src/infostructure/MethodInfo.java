package infostructure;

import java.util.List;

public class MethodInfo extends FunctionInfo{
    CallMethodInfo[] call_methods;
    VariableInfo[] external_fields;
    String return_type;

    public MethodInfo(String sig, 
                      List<VariableInfo> param, 
                      CallMethodInfo[] cmethods,
                      VariableInfo[] fields,
                      String rtn_type) {
        super(sig, param);
        this.call_methods = cmethods;
        this.external_fields = fields;
        this.return_type = rtn_type;
    }
}
