# A constraint the BACS scheduler admitted for transmission, with the decision
# variables the fusion server and the ablation logging need.
builtin_interfaces/Time  stamp
uint32                   cid
uint16                   robot_from
uint16                   robot_to
uint32                   idx_from
uint32                   idx_to
geometry_msgs/Pose2D     z
float32[9]               information
uint16                   payload_bytes
float32                  predicted_trust    # theta_hat, Eq. (9)
float32                  info_score         # I_hat, Eq. (12) [+ observability]
float32                  predicted_delay    # dt_hat [s], Eq. (5)
float32                  queue_age          # windows already deferred
float32                  airtime_cost       # T_air [s], Eq. (4)
