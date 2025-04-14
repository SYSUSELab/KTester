package infostructure;

public class VariableInfo {
    public String variable_name;
    public String variable_type;
    public VariableInfo(String variableName, String vairableType) {
        this.variable_name = variableName;
        this.variable_type = vairableType;
    }

    @Override
    public boolean equals(Object obj) {
        if (this == obj) return true;
        if (obj == null || getClass() != obj.getClass()) return false;
        VariableInfo that = (VariableInfo) obj;
        return variable_name.equals(that.variable_name) && 
            variable_type.equals(that.variable_type);
    }

    @Override
    public int hashCode() {
        return (variable_name+variable_type).hashCode();
    }
}
