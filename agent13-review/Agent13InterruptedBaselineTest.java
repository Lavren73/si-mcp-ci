package si.edt.mcp.server.toolkit.ops;

import static org.junit.Assert.*;
import java.lang.reflect.Proxy;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Stream;
import org.eclipse.core.resources.IMarker;
import org.eclipse.core.resources.IProject;
import org.junit.Test;
import com._1c.g5.v8.dt.validation.marker.IMarkerManager;

public class Agent13InterruptedBaselineTest {
  private static IMarkerManager empty(AtomicInteger calls) {
    return (IMarkerManager) Proxy.newProxyInstance(IMarkerManager.class.getClassLoader(), new Class<?>[]{IMarkerManager.class},
      (p,m,a) -> { if (m.getName().equals("markers")) { calls.incrementAndGet(); return Stream.empty(); }
        if (m.getReturnType()==boolean.class) return false;
        if (m.getReturnType()==int.class) return 0;
        if (m.getReturnType()==long.class) return 0L;
        return null; });
  }
  private static IProject project(AtomicInteger calls) {
    return (IProject) Proxy.newProxyInstance(IProject.class.getClassLoader(),new Class<?>[]{IProject.class},
      (p,m,a) -> { switch(m.getName()) {
        case "getName": return "Agent13FakeProject";
        case "exists": case "isOpen": return true;
        case "findMarkers": calls.incrementAndGet(); return new IMarker[0];
      } if (m.getReturnType()==boolean.class) return false;
        if (m.getReturnType()==int.class) return 0;
        if (m.getReturnType()==long.class) return 0L;
        return null; });
  }
  @Test public void baselineRefusesInterruptedEmptyRetryWithoutPretendingSnapshot() {
    AtomicInteger markerCalls=new AtomicInteger(); AtomicInteger eclipseCalls=new AtomicInteger();
    IProject[] projects={project(eclipseCalls)};
    Thread.currentThread().interrupt();
    try {
      ProjectProblemsReader.BaselineSnapshot x=ProjectProblemsReader.collectBaselineSnapshot(empty(markerCalls),null,projects,"Agent13FakeProject",List.of(),true);
      assertNotNull("agent13 baseline must refuse",x.refusal);
      assertTrue("agent13 explicit failure",x.refusal.startsWith("# Request Failed"));
      assertEquals("agent13 no retry after interrupt",1,markerCalls.get());
      assertEquals("agent13 no eclipse scan after interrupt",0,eclipseCalls.get());
      assertTrue("agent13 interrupt preserved",Thread.currentThread().isInterrupted());
    } finally { Thread.interrupted(); }
  }
  @Test public void baselineHealthyControlReturnsSnapshot() {
    AtomicInteger markerCalls=new AtomicInteger(); AtomicInteger eclipseCalls=new AtomicInteger();
    ProjectProblemsReader.BaselineSnapshot x=ProjectProblemsReader.collectBaselineSnapshot(empty(markerCalls),null,new IProject[]{project(eclipseCalls)},"Agent13FakeProject",List.of(),false);
    assertNull("healthy baseline succeeds",x.refusal); assertTrue(x.diagnostics.isEmpty());
    assertFalse(x.capped); assertEquals(1,markerCalls.get()); assertEquals(1,eclipseCalls.get());
  }
  @Test public void laterInterruptAfterFirstRetryAlsoFailsClosed() {
    AtomicInteger calls=new AtomicInteger();
    try {
      try {
        ProjectProblemsReader.retryEmptyRead(() -> { if(calls.incrementAndGet()==2) Thread.currentThread().interrupt(); return List.of(); });
        fail("agent13 later interrupt must fail");
      } catch(ProjectProblemsReader.MarkerStoreException e) {
        assertTrue(Thread.currentThread().isInterrupted()); assertEquals(2,calls.get());
        assertTrue(e.getCause() instanceof InterruptedException);
      }
    } finally { Thread.interrupted(); }
  }
}
