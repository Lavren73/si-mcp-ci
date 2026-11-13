package si.edt.mcp.server.wire;

import static org.junit.Assert.*;
import java.util.List;
import java.util.Map;
import org.junit.Test;
import si.edt.mcp.server.toolkit.IMcpTool;
import si.edt.mcp.server.toolkit.McpToolCatalog;

public class Agent13Pr197IsolationSentinelTest {
  @Test public void preservesIdentityAndAliasAfterSetupOrInjectedFailure() {
    McpToolCatalog catalog = McpToolCatalog.getInstance();
    final String id = "agent13_unique_isolation_4fe1";
    final String alias = "agent13_alias_isolation_4fe1";
    IMcpTool before = new IMcpTool() {
      public String getName() { return id; }
      public List<String> getAliases() { return List.of(alias); }
      public String getDescription() { return "synthetic isolated sentinel"; }
      public String getInputSchema() { return "{}"; }
      public String execute(Map<String,String> p) { return ""; }
    };
    catalog.register(before);
    assertSame("pre-id", before, catalog.getTool(id));
    assertSame("pre-alias", before, catalog.getTool(alias));
    DiagnosticsCompletenessWireTest fixture = new DiagnosticsCompletenessWireTest();
    boolean injected = Boolean.getBoolean("agent13.setupFailure");
    try {
      if (injected) {
        try { fixture.setUp(); fail("injection did not fire"); }
        catch (IllegalStateException ex) { assertEquals("agent13 setup failure", ex.getMessage()); }
      } else {
        fixture.setUp();
      }
      fixture.tearDown();
      fixture.tearDown();
      assertSame("agent13 identity lost", before, catalog.getTool(id));
      assertSame("agent13 alias lost", before, catalog.getTool(alias));
    } finally { catalog.unregister(id); }
  }
}
