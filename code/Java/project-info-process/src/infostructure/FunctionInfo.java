package infostructure;

import java.util.List;
import com.github.javaparser.ast.AccessSpecifier;

public class FunctionInfo {
    public String signature;
    public VariableInfo[] parameters;
    int start_line;
    int end_line;
    AccessSpecifier access_type;
    // public String body;
    public FunctionInfo(String signature, List<VariableInfo> parameters, int[] position, AccessSpecifier access_type) {
        this.signature = signature;
        this.parameters = parameters.toArray(new VariableInfo[0]);
        this.start_line = position[0];
        this.end_line = position[1];
        this.access_type = access_type;
        // this.body = body;
    }
}
