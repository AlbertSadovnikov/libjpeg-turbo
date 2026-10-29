if(NOT DEFINED INPUT OR NOT DEFINED OUTPUT)
  message(FATAL_ERROR "embed_frame.cmake requires INPUT and OUTPUT")
endif()
file(READ "${INPUT}" HEX HEX)
string(LENGTH "${HEX}" LENGTH)
if(LENGTH EQUAL 0)
  message(FATAL_ERROR "The embedded frame is empty: ${INPUT}")
endif()
file(WRITE "${OUTPUT}"
  "// Generated from the JPEG fixture. Do not edit.\n"
  "#include \"embedded_frame.h\"\n"
  "namespace mjpeg_bench {\nalignas(64) const unsigned char kJpeg[] = {\n")
# Bounded lines avoid compiler line-length limits and require no Python/xxd.
set(OFFSET 0)
while(OFFSET LESS LENGTH)
  math(EXPR REMAINING "${LENGTH} - ${OFFSET}")
  if(REMAINING GREATER 1024)
    set(REMAINING 1024)
  endif()
  string(SUBSTRING "${HEX}" ${OFFSET} ${REMAINING} CHUNK)
  string(REGEX REPLACE "([0-9a-fA-F][0-9a-fA-F])" "0x\\1," CHUNK "${CHUNK}")
  file(APPEND "${OUTPUT}" "${CHUNK}\n")
  math(EXPR OFFSET "${OFFSET} + ${REMAINING}")
endwhile()
file(APPEND "${OUTPUT}"
  "};\nconst std::size_t kJpegSize = sizeof(kJpeg);\n}  // namespace mjpeg_bench\n")
