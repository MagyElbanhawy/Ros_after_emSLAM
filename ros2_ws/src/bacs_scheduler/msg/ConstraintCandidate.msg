# A candidate inter-robot constraint offered to the BACS scheduler.
builtin_interfaces/Time  stamp          # time the candidate was created
uint32                   cid            # candidate id, unique per robot
uint16                   robot_from     # transmitting robot id
uint16                   robot_to       # peer robot id
uint32                   idx_from       # pose-graph node index on the transmitter
uint32                   idx_to         # pose-graph node index on the peer
geometry_msgs/Pose2D     z              # measured relative transform (x, y, theta)
float32[9]               information     # 3x3 measurement information matrix, row-major
uint16                   payload_bytes  # serialised size of the constraint packet
float32                  novelty        # coverage novelty term for Eq. (12)
float32                  degree         # normalised local node degree
float32                  loop_len       # normalised loop length
