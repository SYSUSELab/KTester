package infostructure;

import java.util.List;

public class CallMethodInfo {
    String signature;
    VariableInfo[] arguments;
    String return_type;

    public CallMethodInfo(String sig, List<VariableInfo> arguments, String rtn) {
        this.signature = sig;
        this.arguments = arguments.toArray(new VariableInfo[0]);
        this.return_type = rtn;
    }

    public String getSignature() {
        return signature;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (obj == null || getClass() != obj.getClass()) return false;
        CallMethodInfo that = (CallMethodInfo) obj;
        return signature.equals(that.signature);
    }

    @Override
    public int hashCode() {
        return signature.hashCode();
    }
}
