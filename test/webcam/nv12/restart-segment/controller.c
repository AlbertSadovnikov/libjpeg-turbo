/* Appended to the generated native entropy TU; original core is untouched. */
#include "jdcoefct.h"
#include "/home/al/src/libjpeg-turbo/test/webcam/nv12/fused-chroma/fusion.h"
#include "/home/al/src/libjpeg-turbo/test/webcam/nv12/memset-call/clear.h"

int mjpeg_segment_enabled;

LOCAL(void)
segment_load(j_decompress_ptr c, huff_entropy_ptr entropy,
             bitread_working_state *work, savable_state *predictors)
{
  work->cinfo = c;
  work->next_input_byte = c->src->next_input_byte;
  work->bytes_in_buffer = c->src->bytes_in_buffer;
  work->get_buffer = entropy->bitstate.get_buffer;
  work->bits_left = entropy->bitstate.bits_left;
  *predictors = entropy->saved;
}

LOCAL(void)
segment_commit(j_decompress_ptr c, huff_entropy_ptr entropy,
               const bitread_working_state *work,
               const savable_state *predictors)
{
  c->src->next_input_byte = work->next_input_byte;
  c->src->bytes_in_buffer = work->bytes_in_buffer;
  entropy->bitstate.get_buffer = work->get_buffer;
  entropy->bitstate.bits_left = work->bits_left;
  entropy->saved = *predictors;
}

METHODDEF(int)
segment_data(j_decompress_ptr c, JSAMPIMAGE output)
{
  my_coef_ptr coef = (my_coef_ptr)c->coef;
  huff_entropy_ptr entropy = (huff_entropy_ptr)c->entropy;
  JDIMENSION col = coef->MCU_ctr;
  while (col < c->MCUs_per_row) {
    unsigned count, fast_count, done;
    bitread_working_state work;
    savable_state predictors;
    if (!entropy->restarts_to_go && !process_restart(c))
      goto suspend;
    count = c->MCUs_per_row - col;
    if (count > entropy->restarts_to_go)
      count = entropy->restarts_to_go;
    fast_count = count - (count == entropy->restarts_to_go);
    segment_load(c, entropy, &work, &predictors);
    for (done = 0; done < count; done++) {
      mjpeg_clear_experiment(coef->MCU_buffer[0], 4 * sizeof(JBLOCK));
      if (!entropy->pub.insufficient_data) {
        boolean usefast;
        c->master->last_good_iMCU_row = c->input_iMCU_row;
        usefast = done < fast_count && work.bytes_in_buffer >= 4 * 512 + 8 &&
                  c->unread_marker == 0;
        if (!usefast || !segment_fast(c, coef->MCU_buffer, &work, &predictors)) {
          /* Restore only completed-MCU progress. Fast abort leaves work and
           * predictors intact; partial coefficient output must be discarded.
           * Raw one-pass allocation is contiguous, unlike virtual arrays.
           */
          if (usefast)
            mjpeg_clear_experiment(coef->MCU_buffer[0], 4 * sizeof(JBLOCK));
          segment_commit(c, entropy, &work, &predictors);
          if (!decode_mcu_slow(c, coef->MCU_buffer)) {
            /* Do not overwrite source-manager state after a suspended read. */
            entropy->restarts_to_go -= done;
            goto suspend;
          }
          segment_load(c, entropy, &work, &predictors);
        }
      }
      if (!mjpeg_fusion_mcu(c, coef->MCU_buffer, output, col))
        ERREXIT(c, JERR_NOT_COMPILED);
      col++;
    }
    segment_commit(c, entropy, &work, &predictors);
    entropy->restarts_to_go -= count;
  }
  coef->MCU_ctr = 0;
  c->output_iMCU_row++;
  if (++c->input_iMCU_row < c->total_iMCU_rows) {
    start_iMCU_row(c);
    return JPEG_ROW_COMPLETED;
  }
  (*c->inputctl->finish_input_pass)(c);
  return JPEG_SCAN_COMPLETED;
suspend:
  coef->MCU_ctr = col;
  coef->MCU_vert_offset = 0;
  return JPEG_SUSPENDED;
}

GLOBAL(int)
mjpeg_segment_install(j_decompress_ptr c)
{
  int i;
  if (!mjpeg_segment_enabled || c->restart_interval <= 1 ||
      c->data_precision != 8 || !c->raw_data_out ||
      c->dct_method != JDCT_IFAST || c->progressive_mode || c->arith_code ||
      c->jpeg_color_space != JCS_YCbCr || c->num_components != 3 ||
      c->comps_in_scan != 3 || c->blocks_in_MCU != 4 ||
      c->max_h_samp_factor != 2 || c->max_v_samp_factor != 1 ||
      c->image_width % 16 || c->image_height % 8 ||
      c->output_width != c->image_width || c->output_height != c->image_height ||
      c->coef->coef_arrays != NULL ||
      c->master->first_iMCU_col != 0 ||
      c->master->last_iMCU_col != c->MCUs_per_row - 1 ||
      !__builtin_cpu_supports("avx2") || !__builtin_cpu_supports("fma"))
    return 0;
  for (i = 0; i < 3; i++)
    if (c->cur_comp_info[i] != &c->comp_info[i] ||
        c->comp_info[i]._DCT_scaled_size != 8 ||
        c->comp_info[i].MCU_height != 1 ||
        c->comp_info[i].MCU_width != (i == 0 ? 2 : 1))
      return 0;
  c->coef->decompress_data = segment_data;
  return 1;
}
