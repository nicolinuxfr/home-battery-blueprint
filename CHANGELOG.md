# Changelog

## 2026.6.1

- Better charging when solar powered batteries are at 100 % ;
- To help the automations, a new option is added for solar powered batteries.

## 2026.6.0

- Fix discharge not always starting after peak hours.

## 2026.5.2

- Fix discharge allocation.

## 2026.5.1

- Blueprint simplification : no more reactive battery, the cooldown field is the only one needed. 

## 2026.5.0

- Better handling of off-peak hours charging.

## 2026.4.9

- Huge simplification of the charging during off-peak hours.

## 2026.4.8

- Add an explicit option for responsive batteries.

## 2026.4.7

- Add the ability to charge the battery during off-peak hours ;
- Refactor : more files, shorter.

## 2026.4.6

- Finer adjustments to be closer to 0 W and bug fixes.

## 2026.4.5

- Big simplification of the logic :
  - No more priority battery, the SOC is only used ;
  - The cooldown chooses the allocation : the slow batteries gets a conservative setpoint that won't move often, while the quick batteries fill the gaps.

## 2026.4.4

- Many bug fixes in the handling of batteries.

## 2026.4.3

- A battery that goes above 90 % is now considered a priority.

## 2026.4.2

- New strategy to minimise losses ;
- Adding some logs to check what happens.

## 2026.4.1

- Should export less energy.

## 2026.4

- Initial version.
