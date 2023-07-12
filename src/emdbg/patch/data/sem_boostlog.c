// Copyright (c) 2023, Auterion AG
// SPDX-License-Identifier: BSD-3-Clause

#include <semaphore_boostlog.h>

struct nxsem_boostlog_t
{
  uint32_t used;
  uint16_t dropped;
  nxsem_boostlog_item_t slots[32];
}
nxsem_boostlog;

int nxsem_boostlog_push(nxsem_boostlog_item_t *item)
{
  if (~nxsem_boostlog.used == 0) {
    nxsem_boostlog.dropped++;
    return -1;
  }
  const uint8_t slot = __builtin_ffs(~nxsem_boostlog.used) - 1u;
  nxsem_boostlog.slots[slot] = *item;
  __atomic_or_fetch(&nxsem_boostlog.used, (1u << slot), __ATOMIC_SEQ_CST);
  return 0;
}

int nxsem_boostlog_pop(nxsem_boostlog_item_t *item)
{
  if (nxsem_boostlog.used == 0) return -1;
  const uint8_t slot = __builtin_ffs(nxsem_boostlog.used) - 1u;
  *item = nxsem_boostlog.slots[slot];
  __atomic_and_fetch(&nxsem_boostlog.used, ~(1u << slot), __ATOMIC_SEQ_CST);
  return nxsem_boostlog.dropped;
}
