; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x43 (bvadd independent_opaque_0 independent_opaque_1)))
(let ((?x45 (bvadd independent_opaque_1 independent_opaque_0)))
(and (distinct ?x45 ?x43) true))))
(check-sat)
