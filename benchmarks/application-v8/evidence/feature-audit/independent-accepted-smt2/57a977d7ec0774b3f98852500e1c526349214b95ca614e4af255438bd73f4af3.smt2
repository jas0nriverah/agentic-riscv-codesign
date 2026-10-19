; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x13 (bvadd independent_opaque_0 independent_opaque_1)))
(let ((?x34 (bvadd independent_opaque_1 independent_opaque_0)))
(and (distinct ?x34 ?x13) true))))
(check-sat)
