"""Emit only fixed labels and counters from surefire XML. No paths or error text."""
import glob
import re
import sys
import xml.etree.ElementTree as ET

KNOWN_METHODS = {
    'si.edt.mcp.server.ops.DcsWorkshopToolNoEDTTest#addFieldWithoutProjectNameReturnsError',
    'si.edt.mcp.server.ops.DcsWorkshopToolNoEDTTest#addFieldWithoutTemplatePathReturnsError',
    'si.edt.mcp.server.ops.DcsWorkshopToolNoEDTTest#dryRunOnNonexistentTemplateReturnsTemplateError',
    'si.edt.mcp.server.ops.DcsWorkshopToolParameterizedTest#dryRunValues_doNotCrash',
    'si.edt.mcp.server.ops.DcsWorkshopToolParameterizedTest#knownOperations_doNotCrash',
    'si.edt.mcp.server.ops.DcsWorkshopToolParameterizedTest#missingRequiredParameter_returnsError',
    'si.edt.mcp.server.ops.EditFormToolNoEDTTest#executeWithNoParamsReturnsError',
    'si.edt.mcp.server.settings.AKeptSetOutlivesThePresetChangeTest#aKeptSetIsANameAndCannotOpenTheDoor',
    'si.edt.mcp.server.settings.AKeptSetOutlivesThePresetChangeTest#theBoxesKeptUnderANameComeBackAfterAPresetChange',
    'si.edt.mcp.server.settings.AKeptSetOutlivesThePresetChangeTest#theGroupRowSaysWhatIsLeftAndNotJustHowManyItHolds',
    'si.edt.mcp.server.settings.APresetChangeRepaintsTheHiddenMarksTest#theMarkFollowsThePresetThatWasChosen',
    'si.edt.mcp.server.settings.AQueryBringsBackTheTicksItShowsTest#anEnabledToolComesBackTickedWhenTheQueryReachesIt',
    'si.edt.mcp.server.settings.RestoringToolDefaultsGivesTheShippedPresetTest#theToolsGoBackToThePresetThePluginShipsWith',
}
# The pattern-to-output mapping is fixed, not derived from untrusted XML.
FLAGS = {
    'ASSERTION': r'AssertionError|ComparisonFailure|AssertionFailedError',
    'NO_CLASS_DEF': r'NoClassDefFoundError',
    'CLASS_NOT_FOUND': r'ClassNotFoundException',
    'NULL_POINTER': r'NullPointerException',
    'ILLEGAL_STATE': r'IllegalStateException',
    'SWT_EXCEPTION': r'SWTException|SWTError',
    'SERVICE_UNAVAILABLE': r'ServiceUnavailableException',
    'INITIALIZER_ERROR': r'ExceptionInInitializerError',
    'OSGI_BUNDLE': r'BundleException|BundleActivator|org\.osgi\.framework',
    'JAVA_REFLECTION': r'InvocationTargetException|InaccessibleObjectException',
}


def analyze(paths):
    results = {}
    totals = {'files': len(paths), 'parse_errors': 0, 'other_failure_elements': 0}
    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            totals['parse_errors'] += 1
            continue
        for tc in root.iter('testcase'):
            name = tc.get('classname', '') + '#' + tc.get('name', '')
            for el in tc:
                if el.tag not in ('failure', 'error'):
                    continue
                if name not in KNOWN_METHODS:
                    totals['other_failure_elements'] += 1
                    continue
                # Never print untrusted type, message, body, testcase name, or path.
                text = ' '.join([el.get('type', ''), el.get('message', ''), ''.join(el.itertext())])
                key = (name, el.tag)
                results.setdefault(key, set()).update(k for k, pat in FLAGS.items() if re.search(pat, text))
    return totals, results


def main():
    paths = glob.glob(sys.argv[1], recursive=True)
    totals, results = analyze(paths)
    for key, value in totals.items():
        print('SHAPE_' + key.upper() + '=' + str(value))
    for (method, kind), flags in sorted(results.items()):
        print('SHAPE_METHOD=' + method + ' KIND=' + kind.upper()
              + ' FLAGS=' + (','.join(sorted(flags)) if flags else 'NONE_OF_FIXED_PATTERNS'))
    if not paths or totals['parse_errors']:
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
