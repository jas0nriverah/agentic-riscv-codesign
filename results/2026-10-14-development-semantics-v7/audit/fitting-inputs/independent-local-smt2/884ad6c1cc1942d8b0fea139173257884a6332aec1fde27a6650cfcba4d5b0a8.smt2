(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x38 (bvadd independent_opaque_1 (_ bv17 32))))
(let ((?x51 (bvadd independent_opaque_0 ?x38)))
(let ((?x42 (bvadd ?x38 independent_opaque_0)))
(and (distinct ?x42 ?x51) true)))))
(check-sat)
