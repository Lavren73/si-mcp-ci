"""Print only fixed diagnostic booleans. Do not output any log content."""
import pathlib
import re
import sys

FLAGS = {
 'MISSING_POM': r'(?:non-readable POM|MissingProjectException|specified POM file .* does not exist)',
 'POM_PARSE': r'(?:Non-parseable POM|ModelParseException|ModelBuildingException)',
 'REPOSITORY_RESOLUTION': r'(?:Could not resolve dependencies|Could not resolve artifact|Could not find artifact|Failed to read artifact descriptor|Unresolvable build extension|Non-resolvable)',
 'NETWORK_NAME': r'(?:UnknownHostException|Name or service not known|Temporary failure in name resolution)',
 'NETWORK_TIMEOUT': r'(?:SocketTimeoutException|ConnectTimeoutException|connect timed out|Read timed out)',
 'HTTP_403': r'(?:status code: 403|status: 403|HTTP 403|Forbidden)',
 'HTTP_429': r'(?:status code: 429|status: 429|HTTP 429|Too Many Requests)',
 'HTTP_5XX': r'(?:status code: 5[0-9][0-9]|status: 5[0-9][0-9]|HTTP 5[0-9][0-9])',
 'TLS_FAILURE': r'(?:SSLHandshakeException|PKIX path building failed|certificate_unknown)',
 'CONNECTION_FAILURE': r'(?:ConnectException|Connection refused|Connection reset|Connection timed out)',
 'TYCHO_RESOLUTION': r'(?:Cannot resolve project dependencies|Could not resolve target platform|Failed to resolve target definition|No solution found because the problem is unsatisfiable)',
 'COMPILATION_FAILURE': r'(?:Compilation failure|COMPILATION ERROR)',
 'NO_SPACE': r'(?:No space left on device|Disk quota exceeded)',
 'OOM': r'(?:OutOfMemoryError|Java heap space)',
 'MAVEN_REACTOR_FAILURE': r'BUILD FAILURE',
}

def main(path):
 try: text=pathlib.Path(path).read_text(encoding='utf8',errors='replace')
 except OSError:
  print('MAVEN_LOG_READABLE=false');return 1
 print('MAVEN_LOG_READABLE=true')
 print('MAVEN_LOG_LINES='+str(len(text.splitlines())))
 for name,pattern in FLAGS.items():print('MAVEN_FLAG_'+name+'='+str(bool(re.search(pattern,text,re.I))).lower())
 return 0

if __name__=='__main__':sys.exit(main(sys.argv[1]))
