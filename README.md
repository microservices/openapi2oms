## Assumptions
1. If there are multiple content types available for a given path, the content type
   `application/json` shall be preferred if available. If `application/json` is not
   available, then ANY content type WILL be chosen at random
2. OMG doesn't support multiple responses. As such, the following order of response
   codes are considered as successful operations: `200, 201, 202, 2XX, 204, default`.
   Furthermore, since multiple content types are not supported, `application/json`
   will be used if available. If `application/json` is not available, then ANY content
   type WILL be chosen at random