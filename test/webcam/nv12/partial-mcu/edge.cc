  // Exact-fast edge path: reconstruct a full MCU locally, expose valid pixels.
  // Interior MCUs retain the existing direct writes and transform kernels.
  if(ctx.mode==3 && (col*16+16>c->image_width ||
                    c->input_iMCU_row*8+8>c->image_height)) {
    const unsigned x=col*16, y=c->input_iMCU_row*8;
    const unsigned columns=c->image_width-x<16 ? c->image_width-x : 16;
    const unsigned rows=c->image_height-y<8 ? c->image_height-y : 8;
    alignas(32) unsigned char luma[8][16],chroma[4][16];
    JSAMPROW local_rows[8];
    for(unsigned i=0;i<8;i++)local_rows[i]=luma[i];
    mjpeg_idct_ifast_registers(c->comp_info[0].dct_table,*blocks[0],*blocks[1],local_rows,0);
    mjpeg_chroma_fast_pair(c->comp_info[1].dct_table,c->comp_info[2].dct_table,
                           *blocks[2],*blocks[3],chroma[0],16);
    for(unsigned i=0;i<rows;i++)std::memcpy(output[0][i]+x,luma[i],columns);
    auto *uv=ctx.uv+(y/2)*ctx.pitch+x;
    for(unsigned i=0;i<rows/2;i++)std::memcpy(uv+i*ctx.pitch,chroma[i],columns);
    return 1;
  }
