/*
 * Licensed to the OpenAirInterface (OAI) Software Alliance under one or more
 * contributor license agreements.  See the NOTICE file distributed with
 * this work for additional information regarding copyright ownership.
 * The OpenAirInterface Software Alliance licenses this file to You under
 * the OAI Public License, Version 1.1  (the "License"); you may not use this file
 * except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *      http://www.openairinterface.org/?page_id=698
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 *-------------------------------------------------------------------------------
 * For more information about the OpenAirInterface (OAI) Software Alliance:
 *      contact@openairinterface.org
 */

#include "nr_sdap.h"
#include "assertions.h"
#include "utils.h"
#include <inttypes.h>
#include <pthread.h>
#include <stddef.h>
#include "nr_sdap_entity.h"
#include "common/utils/LOG/log.h"
#include "errno.h"
#include "rlc.h"
#include "tun_if.h"
#include "system.h"

//SERAE add library
#include "/usr/include/linux/tcp.h"
#include "/usr/include/linux/udp.h"
#include "/usr/include/linux/ip.h"
#include "/usr/include/arpa/inet.h"
#include <sys/time.h>

static void reblock_tun_socket(int fd)
{
  int f;

  f = fcntl(fd, F_GETFL, 0);
  f &= ~(O_NONBLOCK);
  if (fcntl(fd, F_SETFL, f) == -1) {
    LOG_E(PDCP, "fcntl(F_SETFL) failed on fd %d: errno %d, %s\n", fd, errno, strerror(errno));
  }
}

  // DRB - DRB + 8 (QFI) - DRB + 3 (LCID)
  // QFI 9  - DRBID 1 - LCID 4
  // QFI 10 - DRBID 2 - LCID 5 **
  // QFI 11 - DRBID 3 - LCID 6 **
  // QFI 12 - DRBID 4 - LCID 7 **
  // QFI 13 - DRBID 5 - LCID 8 **

// SHJIN ADU_header structure: need to identical in sender / receiver files
typedef struct ADU_header_s {
  uint32_t source_ip;
  uint32_t dest_ip;
  unsigned short source_port;
  unsigned short dest_port;
  int ADU_size;
  int ADU_latency;
  uint8_t qfi;
  int req_idx;
} ADU_header_t;

bool sdap_data_req(protocol_ctxt_t *ctxt_p,
                   const ue_id_t ue_id,
                   const srb_flag_t srb_flag,
                   const rb_id_t rb_id,
                   const mui_t mui,
                   const confirm_t confirm,
                   const sdu_size_t sdu_buffer_size,
                   unsigned char *const sdu_buffer,
                   const pdcp_transmission_mode_t pt_mode,
                   const uint32_t *sourceL2Id,
                   const uint32_t *destinationL2Id,
                   const uint8_t qfi,
                   const bool rqi,
                   const int pdusession_id) {
  nr_sdap_entity_t *sdap_entity;
  sdap_entity = nr_sdap_get_entity(ue_id, pdusession_id);

  if(sdap_entity == NULL) {
    LOG_E(SDAP, "%s:%d:%s: Entity not found with ue: 0x%"PRIx64" and pdusession id: %d\n", __FILE__, __LINE__, __FUNCTION__, ue_id, pdusession_id);
    return 0;
  }

  // SHJIN, change QFI to map DRB deliberately
  //uint8_t modi_qfi = qfi;
  if (ctxt_p->enb_flag && !srb_flag){
    if (sdu_buffer_size >= sizeof(struct iphdr)){
      const struct iphdr* ip_header = (struct iphdr*) sdu_buffer;
      unsigned short ip_header_len = ip_header->ihl*4;
      if (sdu_buffer_size >= ip_header_len + sizeof(struct tcphdr)){
        const struct tcphdr* tcp_header = (struct tcphdr*) (sdu_buffer + ip_header_len);
        unsigned short tcp_header_len = tcp_header->doff*4;
        unsigned short dest_port = ntohs(tcp_header->dest);
        if (dest_port > 8000){
          // ADU adu if it is ADU flow
          if (sdu_buffer_size >= ip_header_len + tcp_header_len + sizeof(ADU_header_t)){
            // check is first ADU_packet?
            const ADU_header_t* ADU_header = (ADU_header_t *) (sdu_buffer + ip_header_len + tcp_header_len);
            if (ip_header->saddr == ADU_header->source_ip) {
              struct timespec ts;
              clock_gettime(CLOCK_MONOTONIC, &ts);
              LOG_E(SDAP, "[FEEDER],sdap_ADU_first_packet,ue_ip,%u,port,%hu,req_idx,%d,start_time,%ld.%09ld,size,%d,latency,%d,\n", ADU_header->dest_ip, dest_port, ADU_header->req_idx, ts.tv_sec, ts.tv_nsec, ADU_header->ADU_size, ADU_header->ADU_latency);
            }
          }
        }
      }
    }
  }

  bool ret = sdap_entity->tx_entity(sdap_entity,
                                    ctxt_p,
                                    srb_flag,
                                    rb_id,
                                    mui,
                                    confirm,
                                    sdu_buffer_size,
                                    sdu_buffer,
                                    pt_mode,
                                    sourceL2Id,
                                    destinationL2Id,
                                    qfi,
                                    rqi);
  return ret;
}

void sdap_data_ind(rb_id_t pdcp_entity,
                   int is_gnb,
                   bool has_sdap_rx,
                   int pdusession_id,
                   ue_id_t ue_id,
                   char *buf,
                   int size) {
  nr_sdap_entity_t *sdap_entity;
  sdap_entity = nr_sdap_get_entity(ue_id, pdusession_id);

  if (sdap_entity == NULL) {
    LOG_E(SDAP, "%s:%d:%s: Entity not found for ue rnti/ue_id: %lx and pdusession id: %d\n", __FILE__, __LINE__, __FUNCTION__, ue_id, pdusession_id);
    return;
  }

  sdap_entity->rx_entity(sdap_entity,
                         pdcp_entity,
                         is_gnb,
                         has_sdap_rx,
                         pdusession_id,
                         ue_id,
                         buf,
                         size);
}

static void *sdap_tun_read_thread(void *arg)
{
  DevAssert(arg != NULL);
  nr_sdap_entity_t *entity = arg;

  char rx_buf[NL_MAX_PAYLOAD];
  int len;
  reblock_tun_socket(entity->pdusession_sock);

  int rb_id = 1;

  while (!entity->stop_thread) {
    len = read(entity->pdusession_sock, &rx_buf, NL_MAX_PAYLOAD);
    if (len == -1) {
      if (errno == EINTR)
        continue; // interrupted system call

      if (errno == EBADF || errno == EINVAL) {
        LOG_I(SDAP, "Socket closed, exiting TUN read thread for UE %ld, PDU session %d\n", entity->ue_id, entity->pdusession_id);
        break;
      }

      LOG_E(PDCP, "read() failed: errno %d (%s)\n", errno, strerror(errno));
      break;
    }

    if (len == 0) {
      LOG_W(SDAP, "TUN socket returned EOF - exiting thread\n");
      break;
    }

    LOG_D(SDAP, "read data of size %d\n", len);

    protocol_ctxt_t ctxt = {.enb_flag = entity->is_gnb, .rntiMaybeUEid = entity->ue_id};

    bool dc = entity->is_gnb ? false : SDAP_HDR_UL_DATA_PDU;

    DevAssert(entity != NULL);
    entity->tx_entity(entity,
                      &ctxt,
                      SRB_FLAG_NO,
                      rb_id,
                      RLC_MUI_UNDEFINED,
                      RLC_SDU_CONFIRM_NO,
                      len,
                      (unsigned char *)rx_buf,
                      PDCP_TRANSMISSION_MODE_DATA,
                      NULL,
                      NULL,
                      entity->qfi,
                      dc);
  }

  return NULL;
}

void start_sdap_tun_gnb_first_ue_default_pdu_session(ue_id_t ue_id)
{
  nr_sdap_entity_t *entity = nr_sdap_get_entity(ue_id, get_softmodem_params()->default_pdu_session_id);
  DevAssert(entity != NULL);
  DevAssert(entity->is_gnb);
  char *ifprefix = get_softmodem_params()->nsa ? "oaitun_gnb" : "oaitun_enb";
  char ifname[IFNAMSIZ];
  tun_generate_ifname(ifname, ifprefix, ue_id - 1);
  entity->pdusession_sock = tun_alloc(ifname);
  tun_config(ifname, "10.0.1.1", NULL);
  threadCreate(&entity->pdusession_thread, sdap_tun_read_thread, entity, "gnb_tun_read_thread", -1, OAI_PRIORITY_RT_LOW);
}

void start_sdap_tun_ue(ue_id_t ue_id, int pdu_session_id, int sock)
{
  nr_sdap_entity_t *entity = nr_sdap_get_entity(ue_id, pdu_session_id);
  DevAssert(entity != NULL);
  DevAssert(!entity->is_gnb);
  entity->pdusession_sock = sock;
  entity->stop_thread = false;
  char thread_name[64];
  snprintf(thread_name, sizeof(thread_name), "ue_tun_read_%ld_p%d", ue_id, pdu_session_id);
  threadCreate(&entity->pdusession_thread, sdap_tun_read_thread, entity, thread_name, -1, OAI_PRIORITY_RT_LOW);
}


void create_ue_ip_if(const char *ipv4, const char *ipv6, int ue_id, int pdu_session_id)
{
  int default_pdu = get_softmodem_params()->default_pdu_session_id;
  char ifname[IFNAMSIZ];
  tun_generate_ue_ifname(ifname, ue_id, pdu_session_id != default_pdu ? pdu_session_id : -1);
  const int sock = tun_alloc(ifname);
  tun_config(ifname, ipv4, ipv6);
  if (ipv4) {
    setup_ue_ipv4_route(ifname, ue_id, ipv4);
  }
  start_sdap_tun_ue(ue_id, pdu_session_id, sock); // interface name suffix is ue_id+1
}

void remove_ip_if(nr_sdap_entity_t *entity)
{
  DevAssert(entity != NULL);
  // Stop the read thread
  entity->stop_thread = true;

  // Close the socket: read() will get EBADF and exit
  close(entity->pdusession_sock);

  int ret = pthread_join(entity->pdusession_thread, NULL);
  AssertFatal(ret == 0, "pthread_join() failed, errno: %d, %s\n", errno, strerror(errno));
  // Bring down the IP interface
  int default_pdu = get_softmodem_params()->default_pdu_session_id;
  char ifname[IFNAMSIZ];
  if (entity->is_gnb) {
    char *ifprefix = get_softmodem_params()->nsa ? "oaitun_gnb" : "oaitun_enb";
    tun_generate_ifname(ifname, ifprefix, entity->ue_id - 1);
  } else {
    tun_generate_ue_ifname(ifname, entity->ue_id, entity->pdusession_id != default_pdu ? entity->pdusession_id : -1);
  }
  tun_destroy(ifname);
}
