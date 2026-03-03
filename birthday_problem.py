import numpy as np

# Keep this close to your original approach.
DAYS_IN_YEAR = 365
np.random.seed(42)  # optional reproducibility

num_people_arr = [10 * n for n in range(15)]
num_trials = int(1e5)

for num_people in num_people_arr:
    collision_present = 0

    for _ in range(num_trials):
        # randint upper bound is exclusive, so use 366 to include day 365.
        birthdates = np.random.randint(1, 366, size=num_people)
        if len(np.unique(birthdates)) != len(birthdates):
            collision_present += 1

    theoretical_answer = 1.0
    for ki in range(num_people):
        theoretical_answer *= (DAYS_IN_YEAR - ki) / DAYS_IN_YEAR
    theoretical_answer = 1 - theoretical_answer

    print(f"num_people={num_people}")
    print("  Experimental result:", collision_present / num_trials)
    print("  Theoretical result: ", theoretical_answer)
    print()

# Probability of at least one collision:
# 1 - [n! / ((n-k)! * n^k)] for n=365, k=num_people
