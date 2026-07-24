# Periodic radio / link telemetry the scheduler uses to predict delay and trust.
builtin_interfaces/Time  stamp
float32                  duty_cycle          # delta, regulatory ceiling
float32                  airtime_used_window # airtime consumed in the current window [s]
float32                  loss_rate_ewma      # p_loss estimate from acknowledgements
float32                  mean_delay_ewma     # measured mean end-to-end delay [s]
float32                  map_age             # age of the last fused map received [s]
