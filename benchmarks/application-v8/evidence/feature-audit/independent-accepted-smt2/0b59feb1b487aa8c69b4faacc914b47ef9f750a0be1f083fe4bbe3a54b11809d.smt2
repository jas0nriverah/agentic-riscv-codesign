; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x54 (bvadd independent_opaque_0 (bvsub (_ bv0 32) independent_opaque_1))))
(let ((?x595 (bvsub independent_opaque_0 independent_opaque_1)))
(and (distinct ?x595 ?x54) true))))
(check-sat)
