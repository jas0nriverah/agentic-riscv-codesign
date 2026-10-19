; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x16 (bvadd independent_opaque_0 independent_opaque_1)))
(let ((?x11 (bvadd independent_opaque_1 independent_opaque_0)))
(and (distinct ?x11 ?x16) true))))
(check-sat)
