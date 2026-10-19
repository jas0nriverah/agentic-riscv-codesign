(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x183 (bvshl y (_ bv15 32))))
(let ((?x179 (bvshl x (_ bv15 32))))
(let ((?x186 (bvsub ?x179 ?x183)))
(let ((?x24 (bvsub x y)))
(let ((?x185 (bvshl ?x24 (_ bv15 32))))
(and (distinct ?x185 ?x186) true)))))))
(check-sat)
