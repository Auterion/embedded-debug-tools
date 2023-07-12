// Copyright (c) 2023, Auterion AG
// SPDX-License-Identifier: BSD-3-Clause

#ifndef __INCLUDE_SEMAPHORE_BOOSTLOG_H
#define __INCLUDE_SEMAPHORE_BOOSTLOG_H

#include <semaphore.h>

#ifdef __cplusplus
extern "C"
{
#endif

typedef struct
{
  uint64_t hrt;
  sem_t *sem;
  char name[24];
  char reason[24];
  uint8_t prio_from;
  uint8_t prio_to;
  uint16_t line;
}
nxsem_boostlog_item_t;

int nxsem_boostlog_push(nxsem_boostlog_item_t *item);

int nxsem_boostlog_pop(nxsem_boostlog_item_t *item);

#define NX_SEMBOOST_LOG_PUSH_UP(rtcb) \
  { \
    nxsem_boostlog_item_t item = { \
      .hrt = hrt_absolute_time(), \
      .sem = sem, \
      .prio_from = htcb->sched_priority, \
      .prio_to = rtcb->sched_priority, \
      .line = __LINE__ \
    }; \
    strncpy(item.name, htcb->name, sizeof(item.name) - 1); \
    strncpy(item.reason, rtcb->name, sizeof(item.reason) - 1); \
    nxsem_boostlog_push(&item); \
  }

#define NX_SEMBOOST_LOG_PUSH_DOWN(prio) \
  { \
    nxsem_boostlog_item_t item = { \
      .hrt = hrt_absolute_time(), \
      .sem = sem, \
      .prio_from = htcb->sched_priority, \
      .prio_to = prio, \
      .line = __LINE__ \
    }; \
    strncpy(item.name, htcb->name, sizeof(item.name) - 1); \
    nxsem_boostlog_push(&item); \
  }

#ifdef __cplusplus
}
#endif

#endif /* __INCLUDE_SEMAPHORE_BOOSTLOG_H */
